"""Accounts: bcrypt hashes, JWT login, protected routes."""

from __future__ import annotations

import sqlite3

import settings
from conftest import new_user


def test_register_returns_a_token_and_hashes_the_password(client):
    u = new_user(client, "hash")
    conn = sqlite3.connect(settings.db_path())
    stored = conn.execute("SELECT password_hash FROM users WHERE username = ?", (u["username"],)).fetchone()[0]
    conn.close()
    assert stored.startswith("$2") and "secret123" not in stored


def test_duplicate_username_is_rejected(client, user):
    res = client.post("/db/auth/register", json={"username": user["username"], "password": "another1"})
    assert res.status_code == 409


def test_login_with_the_right_and_wrong_password(client, user):
    ok = client.post("/db/auth/login", json={"username": user["username"], "password": "secret123"})
    assert ok.status_code == 200 and ok.json()["access_token"]
    bad = client.post("/db/auth/login", json={"username": user["username"], "password": "wrongpass"})
    assert bad.status_code == 401


def test_demo_account_is_seeded(client):
    res = client.post("/db/auth/login", json={"username": "demo", "password": "demo123"})
    assert res.status_code == 200


def test_me_needs_a_valid_token(client, user):
    assert client.get("/db/auth/me").status_code == 401
    assert client.get("/db/auth/me", headers={"Authorization": "Bearer not-a-token"}).status_code == 401
    assert client.get("/db/auth/me", headers=user["headers"]).json()["username"] == user["username"]


def test_model_training_needs_login(client):
    assert client.post("/models/train").status_code == 401
