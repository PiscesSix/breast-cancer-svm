"""Compare the five classifiers and save reports/comparison.json (read by the API and the report).

Run:  python scripts/train_comparison.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import comparison  # noqa: E402


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    report = comparison.train_all()
    report["trained_by"] = "scripts/train_comparison.py"
    comparison.save(report)
    best = next(m for m in report["models"] if m["model"] == report["best_model"])
    print(f"[compare] tốt nhất theo CV recall_macro: {best['label']} ({best['cv_mean']:.4f}); "
          f"đã lưu {comparison.REPORT_PATH.relative_to(ROOT)} sau {report['total_seconds']:.1f}s")


if __name__ == "__main__":
    main()
