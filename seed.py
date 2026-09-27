"""Seed the system: demo account and the first five-classifier comparison in the database.

Run:  python seed.py [--retrain]

Idempotent: the comparison is recomputed only with --retrain (or if reports/comparison.json is
missing), the demo account is created only if absent, and the first comparison is copied into
model_runs only while that table is empty. In single-service mode app/main.py calls
`seed_database()` at startup, so a fresh SQLite file on Render gets the demo account back.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys

from app import comparison
from db_api.auth import create_user
from db_api.db import connect
from db_api.runs import TrainingRunIn, store_run

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


def seed_database(report: dict | None = None, log=print) -> None:
    """Create the demo user and store the current comparison table if the DB has none."""
    conn = connect()
    try:
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
    parser = argparse.ArgumentParser(description="Khởi tạo dữ liệu: tài khoản demo + lần so sánh đầu tiên")
    parser.add_argument("--retrain", action="store_true", help="So sánh lại 5 mô hình dù đã có kết quả")
    args = parser.parse_args()
    seed_database(ensure_comparison(args.retrain))
    print("[seed] Xong.")


if __name__ == "__main__":
    main()
