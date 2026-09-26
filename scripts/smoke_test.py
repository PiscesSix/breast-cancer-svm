"""Post-deploy checks of the lecture (slide 32) against any running instance.

Run:  python scripts/smoke_test.py https://<service>.onrender.com
      python scripts/smoke_test.py http://127.0.0.1:8000

Only the standard library is used, so it runs anywhere Python does. Exit code 1 if a check fails.
Two of the seven checks cannot be fully automated from outside: reading Render's logs (step 5) and
restarting the service (step 7); the script checks what is observable and prints what to do by hand.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "sample_request.json"
LOCAL_METADATA = ROOT / "artifacts" / "metadata.json"
COLD_START_SECONDS = 120


def call(base: str, path: str, body: dict | None = None, timeout: float = 60) -> tuple[int, dict | str, dict]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data, method="GET" if body is None else "POST",
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw = res.read().decode("utf-8")
            status, headers = res.status, dict(res.headers)
    except urllib.error.HTTPError as err:
        raw, status, headers = err.read().decode("utf-8"), err.code, dict(err.headers)
    try:
        return status, json.loads(raw), headers
    except json.JSONDecodeError:
        return status, raw, headers


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    base = sys.argv[1].rstrip("/")
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, note: str = "") -> None:
        results.append((name, ok, note))
        print(f"  [{'OK ' if ok else 'FAIL'}] {name}{' — ' + note if note else ''}")

    print(f"Smoke test {base}")
    # 1. Smoke: /health, waiting for a sleeping free instance to wake up.
    deadline = time.time() + COLD_START_SECONDS
    status, health = 0, {}
    while time.time() < deadline:
        try:
            status, health, _ = call(base, "/health", timeout=90)
            if status == 200:
                break
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(5)
    check("1. GET /health trả 200", status == 200 and health.get("model_loaded") is True, f"HTTP {status}")

    # 2. Schema: Swagger page and an OpenAPI schema with the 30 named features.
    status_docs, _, _ = call(base, "/docs")
    _, openapi, _ = call(base, "/openapi.json")
    props = (openapi.get("components", {}).get("schemas", {}).get("BreastCancerFeatures", {})
             .get("properties", {})) if isinstance(openapi, dict) else {}
    check("2. /docs hiển thị, schema có 30 trường", status_docs == 200 and len(props) == 30, f"{len(props)} trường")

    # 3. Prediction with the same payload used locally.
    payload = json.loads(SAMPLE.read_text(encoding="utf-8"))
    status, pred, headers = call(base, "/predict", payload)
    ok = status == 200 and pred.get("predicted_label") in ("malignant", "benign")
    check("3. POST /predict với sample_request.json", ok,
          f"{pred.get('predicted_label')} P(ác tính)={pred.get('probability_malignant')}" if ok else f"HTTP {status}")

    # 4. Negative: a missing feature must give 422 and name it.
    broken = {"features": dict(payload["features"])}
    broken["features"].pop("mean radius")
    status, err, _ = call(base, "/predict", broken)
    check("4. Thiếu trường → 422", status == 422 and err.get("missing") == ["mean radius"], f"HTTP {status}")

    # 5. Logs: the API must not echo the payload back and must tag requests with an id.
    echoed = "input" in json.dumps(err)
    check("5. Không trả lại payload trong lỗi, có X-Request-ID", not echoed and bool(headers.get("x-request-id")),
          "đọc thêm Logs trên Render: chỉ có request_id, path, status, latency")

    # 6. Version: every endpoint agrees on model_version.
    _, meta, _ = call(base, "/metadata")
    versions = {health.get("model_version"), pred.get("model_version"), meta.get("model_version")}
    check("6. model_version thống nhất", len(versions) == 1 and None not in versions, ", ".join(map(str, versions)))

    # 7. Restart: the artifact served is the committed one (same data hash and training date).
    local = json.loads(LOCAL_METADATA.read_text(encoding="utf-8"))
    same = meta.get("data_hash") == local["data_hash"] and meta.get("train_date") == local["train_date"]
    check("7. Artifact nạp lại đúng bản đã commit", same,
          "để kiểm tra khởi động lại: Render > Manual Deploy > Restart service, rồi chạy lại script")

    failed = [r for r in results if not r[1]]
    print(f"\nKết quả: {len(results) - len(failed)}/{len(results)} đạt")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
