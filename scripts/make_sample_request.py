"""Write sample_request.json from the dataset itself, so nobody types 30 feature names by hand.

Uses row 0 of load_breast_cancer (as in the lecture), wrapped as {"features": {...}}.

Run:  python scripts/make_sample_request.py [--row 0]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.train import CLASS_MAPPING, load_data  # noqa: E402

OUT = ROOT / "sample_request.json"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Sinh sample_request.json từ dataset")
    parser.add_argument("--row", type=int, default=0)
    args = parser.parse_args()
    X, y, names, _ = load_data()
    payload = {"features": {name: float(v) for name, v in zip(names, X[args.row], strict=True)}}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Đã ghi {OUT.name}: dòng {args.row} của dataset, nhãn thật {CLASS_MAPPING[str(int(y[args.row]))]}")


if __name__ == "__main__":
    main()
