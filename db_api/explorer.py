"""Read-only database explorer for the web page "Dữ liệu SQL" (ported from da1, SQLite only).

Only the accounts listed in SQL_VIEWER_USERS (default: admin, whose password comes from
ADMIN_PASSWORD) may use it; the public demo account may not. Free SQL runs as a single
statement on a connection switched to PRAGMA query_only, with a 5-second budget, so nothing
can be changed. Table views show the owner's username instead of user_id and never the
password_hash column; free SQL may not name password_hash, and bcrypt hashes are masked in
every result.
"""

from __future__ import annotations

import re
import sqlite3
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

import security
import settings
from db_api.db import get_conn

router = APIRouter(prefix="/sql", tags=["Dữ liệu SQL"])

MAX_ROWS = 500
TIMEOUT_MS = 5000
BCRYPT_RE = re.compile(r"\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}")
LEADING_COMMENTS_RE = re.compile(r"^\s*(?:--[^\n]*\n\s*|/\*.*?\*/\s*)*", re.S)

HIDDEN_COLUMNS = {"user_id", "password_hash"}


def viewer_usernames() -> set[str]:
    """Accounts allowed on the SQL page; these names cannot be registered from the web."""
    return {u.lower() for u in settings.csv_list("SQL_VIEWER_USERS", "admin")}


def sql_viewer(user: dict = Depends(security.current_user)) -> dict:
    if user["username"].lower() not in viewer_usernames():
        raise HTTPException(403, "Chỉ tài khoản quản trị mới được xem CSDL.")
    return user


class QueryIn(BaseModel):
    sql: str = Field(..., min_length=1, max_length=5000,
                     examples=["SELECT diagnosis, COUNT(*) FROM wdbc GROUP BY diagnosis"])


def _plain(value):
    if isinstance(value, str):
        return BCRYPT_RE.sub("•••• (bcrypt)", value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _plain(str(value))


def _result(cursor, rows) -> dict:
    columns = [c[0] for c in cursor.description]
    return {"columns": columns,
            "rows": [[_plain(row[i]) for i in range(len(columns))] for row in rows]}


def _tables(conn) -> list[str]:
    sql = "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    return [r[0] for r in conn.execute(sql)]


def _checked_table(conn, name: str) -> str:
    if name not in _tables(conn):
        raise HTTPException(404, f"Không có bảng '{name}'")
    return '"' + name + '"'  # safe: the name is one of the real table names


def _view_select(conn, quoted: str) -> tuple[str, list[str], str]:
    """SELECT list + FROM clause for a table view: no user_id / password_hash; a table with
    user_id gets the owner's username (LEFT JOIN users) right after its id. Tables that log
    events (created_at) are shown newest first, the dataset table in its natural order."""
    columns = [c[0] for c in conn.execute(f"SELECT * FROM {quoted} LIMIT 0").description]
    shown = [c for c in columns if c not in HIDDEN_COLUMNS]
    select = [f't."{c}"' for c in shown]
    source = f"{quoted} t"
    if "user_id" in columns:
        at = 1 if shown and shown[0] == "id" else 0
        select.insert(at, "u.username AS username")
        shown.insert(at, "username")
        source += " LEFT JOIN users u ON u.id = t.user_id"
    direction = "desc" if "created_at" in columns or "applied_at" in columns else "asc"
    order = 't."id"' if "id" in columns else "1"
    return f"SELECT {', '.join(select)} FROM {source} ORDER BY {order} {direction.upper()}", shown, direction


def describe() -> str:
    return f"SQLite · {settings.db_path().name}"


@router.get("/tables")
def list_tables(user: dict = Depends(sql_viewer), conn=Depends(get_conn)):
    """Every table with its row count and the columns shown on the page."""
    tables = []
    for name in _tables(conn):
        quoted = _checked_table(conn, name)
        count = conn.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
        tables.append({"name": name, "rows": count, "columns": _view_select(conn, quoted)[1]})
    return {"database": describe(), "max_rows": MAX_ROWS, "tables": tables}


@router.get("/tables/{name}")
def read_table(name: str, limit: int = Query(50, ge=1, le=MAX_ROWS), offset: int = Query(0, ge=0),
               user: dict = Depends(sql_viewer), conn=Depends(get_conn)):
    """Rows of one table (log tables newest first), without user_id / password_hash."""
    quoted = _checked_table(conn, name)
    total = conn.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
    select, _, direction = _view_select(conn, quoted)
    cur = conn.execute(f"{select} LIMIT ? OFFSET ?", (limit, offset))
    return {"table": name, "total": total, "limit": limit, "offset": offset, "order": direction,
            **_result(cur, cur.fetchall())}


def _run_read_only(conn: sqlite3.Connection, text: str):
    """Execute one statement that cannot write; returns (cursor, rows, truncated)."""
    conn.execute("PRAGMA query_only = ON")
    deadline = time.perf_counter() + TIMEOUT_MS / 1000
    # SQLite has no statement timeout: a progress handler that returns non-zero interrupts the query.
    conn.set_progress_handler(lambda: int(time.perf_counter() > deadline), 10_000)
    try:
        cur = conn.execute(text)  # sqlite3 refuses more than one statement
        if cur.description is None:
            return cur, [], False
        rows = cur.fetchmany(MAX_ROWS + 1)
    finally:
        conn.set_progress_handler(None, 0)
    return cur, rows[:MAX_ROWS], len(rows) > MAX_ROWS


def _error_message(exc: Exception) -> str:
    text = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
    if "readonly" in text or "read-only" in text:
        return "Trang này chỉ đọc: không chạy được INSERT/UPDATE/DELETE/CREATE/DROP."
    if "one statement" in text:
        return "Mỗi lần chỉ chạy một câu lệnh."
    if "interrupted" in text:
        return f"Câu lệnh chạy quá {TIMEOUT_MS // 1000} giây nên đã bị dừng."
    return f"Lỗi SQL: {text}"


@router.post("/query")
def run_query(body: QueryIn, user: dict = Depends(sql_viewer), conn=Depends(get_conn)):
    """Run one read-only SELECT / WITH statement; at most 500 rows are returned (the rest is cut)."""
    text = body.sql.strip().rstrip(";").strip()
    first = LEADING_COMMENTS_RE.sub("", text).split(None, 1)
    if not first or first[0].lower() not in {"select", "with"}:
        raise HTTPException(400, "Chỉ cho phép câu lệnh đọc dữ liệu (SELECT hoặc WITH).")
    if ";" in text:
        raise HTTPException(400, "Mỗi lần chỉ chạy một câu lệnh (không dùng dấu ; ở giữa).")
    if "password_hash" in text.lower():
        raise HTTPException(400, "Không được truy vấn cột password_hash.")
    started = time.perf_counter()
    try:
        cur, rows, truncated = _run_read_only(conn, text)
    except sqlite3.Error as exc:
        raise HTTPException(400, _error_message(exc)) from None
    elapsed_ms = (time.perf_counter() - started) * 1000
    if cur.description is None:
        return {"columns": [], "rows": [], "truncated": False, "elapsed_ms": round(elapsed_ms, 2)}
    return {**_result(cur, rows), "truncated": truncated, "elapsed_ms": round(elapsed_ms, 2)}
