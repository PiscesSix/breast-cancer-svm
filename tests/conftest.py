"""Shared fixtures: one TestClient for the whole session and ready-made payloads."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

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
