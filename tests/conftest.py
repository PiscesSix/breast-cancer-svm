"""Shared fixtures: the single-service app on a throw-away SQLite database."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Must be set before app / settings are imported.
_TMP = Path(tempfile.mkdtemp(prefix="bc-tests-"))
os.environ["DB_PATH"] = str(_TMP / "test.db")
os.environ["JWT_SECRET"] = "test-secret-key-that-is-long-enough-for-hs256"
os.environ["SERVICE_MODE"] = "single"
os.environ["ADMIN_PASSWORD"] = ADMIN_PASSWORD = "admin-test-pass"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

SAMPLES = {s["id"]: s for s in json.loads((ROOT / "artifacts" / "test_samples.json").read_text(encoding="utf-8"))}


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def features() -> dict[str, float]:
    """A fresh copy of test-000 (true label: malignant) that a test may modify."""
    return dict(SAMPLES["test-000"]["features"])


_counter = {"n": 0}


def new_user(client, prefix: str = "user") -> dict:
    _counter["n"] += 1
    username = f"{prefix}{_counter['n']}"
    res = client.post("/db/auth/register", json={"username": username, "password": "secret123"})
    assert res.status_code == 201, res.text
    body = res.json()
    return {"username": username, "token": body["access_token"],
            "headers": {"Authorization": f"Bearer {body['access_token']}"}}


@pytest.fixture
def user(client):
    return new_user(client)


def prediction_item(features: dict, label: str = "malignant", actual: str | None = "malignant") -> dict:
    return {"model": "svm_rbf", "input": features, "predicted_label": label, "probability_malignant": 0.9,
            "threshold": 0.3993, "actual_label": actual, "sample_id": "test-000", "runtime_ms": 3.2}
