"""Seed the system: demo and admin accounts, the WDBC dataset table and the first five-classifier
comparison in the database.

Run:  python seed.py [--retrain]

Idempotent: the comparison is recomputed only with --retrain (or if reports/comparison.json is
missing), the demo account is created only if absent, the admin account (SQL page) exists only when
ADMIN_PASSWORD is set, the 569 WDBC rows are loaded only while the wdbc table is empty, and the first
comparison is copied into model_runs only while that table is empty. In single-service mode app/main.py calls
`seed_database()` at startup, so a fresh SQLite file on Render gets the demo account back.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys

import numpy as np
from sklearn.model_selection import train_test_split

import security
import settings
from app import comparison
from db_api.auth import create_user
from db_api.db import connect
from db_api.explorer import viewer_usernames
from db_api.runs import TrainingRunIn, store_run
from scripts.train import CLASS_MAPPING, RANDOM_STATE, TEST_SIZE, load_data

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo123"


def ensure_comparison(retrain: bool = False, log=print) -> dict:
    if retrain or not comparison.REPORT_PATH.exists():
        log("[seed] So sánh 5 mô hình phân loại...")
        report = comparison.train_all(log=log)
        report["trained_by"] = "seed"
        comparison.save(report)
        return report
    return comparison.load()


def ensure_admins(conn, log=print) -> None:
    """Create the SQL-page accounts (SQL_VIEWER_USERS) with ADMIN_PASSWORD, or reset their
    password to it; without ADMIN_PASSWORD no such account exists and the page stays closed."""
    password = settings.get("ADMIN_PASSWORD")
    if not password:
        return
    for name in sorted(viewer_usernames()):
        row = conn.execute("SELECT id, password_hash FROM users WHERE username = ?", (name,)).fetchone()
        if row is None:
            try:
                create_user(conn, name, password)
                log(f"[seed] Đã tạo tài khoản quản trị: {name} (mật khẩu = ADMIN_PASSWORD)")
            except sqlite3.IntegrityError:  # created concurrently by another worker
                pass
        elif not security.verify_password(password, row["password_hash"]):
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                         (security.hash_password(password), row["id"]))
            conn.commit()
            log(f"[seed] Đã cập nhật mật khẩu tài khoản quản trị {name} theo ADMIN_PASSWORD")


def wdbc_column(feature: str) -> str:
    """sklearn name -> Kaggle/UCI column: 'mean concave points' -> 'concave_points_mean',
    'radius error' -> 'radius_se', 'worst area' -> 'area_worst'."""
    if feature.startswith("mean "):
        base, suffix = feature.removeprefix("mean "), "mean"
    elif feature.startswith("worst "):
        base, suffix = feature.removeprefix("worst "), "worst"
    else:
        base, suffix = feature.removesuffix(" error"), "se"
    return f"{base.replace(' ', '_')}_{suffix}"


def ensure_wdbc(conn, log=print) -> None:
    """Load the 569 rows of load_breast_cancer into the wdbc table, marking the same train/test
    split as scripts/train.py (test rows get the test-NNN id of artifacts/test_samples.json)."""
    if conn.execute("SELECT COUNT(*) FROM wdbc").fetchone()[0]:
        return
    X, y, names, _ = load_data()
    _, test_idx = train_test_split(np.arange(len(y)), test_size=TEST_SIZE, stratify=y, random_state=RANDOM_STATE)
    sample_id = {int(i): f"test-{k:03d}" for k, i in enumerate(test_idx)}
    columns = ["id", "diagnosis", "split", "sample_id", *map(wdbc_column, names)]
    rows = [(i, CLASS_MAPPING[str(int(y[i]))], "test" if i in sample_id else "train", sample_id.get(i),
             *map(float, X[i])) for i in range(len(y))]
    placeholders = ", ".join("?" * len(columns))
    conn.executemany(f"INSERT OR IGNORE INTO wdbc ({', '.join(columns)}) VALUES ({placeholders})", rows)
    conn.commit()
    log(f"[seed] Đã nạp {len(rows)} mẫu WDBC vào bảng wdbc ({len(sample_id)} mẫu test)")


def seed_database(report: dict | None = None, log=print) -> None:
    """Create the demo and admin users, load the WDBC table and store the current comparison
    table if the DB has none."""
    conn = connect()
    try:
        ensure_admins(conn, log)
        ensure_wdbc(conn, log)
        row = conn.execute("SELECT id FROM users WHERE username = ?", (DEMO_USERNAME,)).fetchone()
        if row is None:
            try:
                user_id = create_user(conn, DEMO_USERNAME, DEMO_PASSWORD)
                log(f"[seed] Đã tạo tài khoản demo: {DEMO_USERNAME} / {DEMO_PASSWORD}")
            except sqlite3.IntegrityError:  # created concurrently by another worker
                user_id = conn.execute("SELECT id FROM users WHERE username = ?", (DEMO_USERNAME,)).fetchone()[0]
        else:
            user_id = row[0]

        if conn.execute("SELECT COUNT(*) FROM training_runs").fetchone()[0] == 0:
            report = report or comparison.load()
            run_id = store_run(conn, user_id, TrainingRunIn(
                trained_at=report["trained_at"],
                train_size=report["data"]["train_size"],
                test_size=report["data"]["test_size"],
                target_sensitivity=report["target_sensitivity"],
                best_model=report["best_model"],
                total_seconds=report.get("total_seconds"),
                models=report["models"],
            ))
            log(f"[seed] Đã lưu bảng so sánh 5 mô hình vào model_runs (lần train #{run_id})")
    finally:
        conn.close()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Khởi tạo dữ liệu: tài khoản demo/admin, bảng wdbc + lần so sánh đầu tiên")
    parser.add_argument("--retrain", action="store_true", help="So sánh lại 5 mô hình dù đã có kết quả")
    args = parser.parse_args()
    seed_database(ensure_comparison(args.retrain))
    print("[seed] Xong.")


if __name__ == "__main__":
    main()
