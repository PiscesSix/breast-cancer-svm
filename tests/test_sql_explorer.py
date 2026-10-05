"""Read-only SQL explorer (/db/sql/*): access control, hidden columns, the WDBC table, no way to write."""

from __future__ import annotations

import pytest

from conftest import ADMIN_PASSWORD, prediction_item


def _login(client, username, password):
    res = client.post("/db/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def admin(client):
    return _login(client, "admin", ADMIN_PASSWORD)


def _query(client, admin, sql):
    return client.post("/db/sql/query", headers=admin, json={"sql": sql})


def _count(client, admin, table):
    return _query(client, admin, f"SELECT COUNT(*) AS n FROM {table}").json()["rows"][0][0]


def test_only_the_admin_account_may_read(client, user):
    assert client.get("/db/sql/tables").status_code == 401
    assert client.get("/db/sql/tables", headers=user["headers"]).status_code == 403
    # The public demo account (password shown on the login page) is not an admin.
    demo = _login(client, "demo", "demo123")
    assert client.get("/db/sql/tables", headers=demo).status_code == 403
    assert client.post("/db/sql/query", headers=demo, json={"sql": "SELECT 1"}).status_code == 403


def test_admin_name_cannot_be_registered(client):
    for name in ("admin", "ADMIN"):
        res = client.post("/db/auth/register", json={"username": name, "password": "secret123"})
        assert res.status_code == 409


def test_wdbc_table_holds_the_dataset_and_the_split(client, admin):
    tables = {t["name"]: t for t in client.get("/db/sql/tables", headers=admin).json()["tables"]}
    assert {"users", "predictions", "training_runs", "model_runs", "wdbc"} <= set(tables)
    assert tables["wdbc"]["rows"] == 569
    assert tables["wdbc"]["columns"][:5] == ["id", "diagnosis", "split", "sample_id", "radius_mean"]
    assert len(tables["wdbc"]["columns"]) == 4 + 30

    counts = dict(_query(client, admin, "SELECT diagnosis, COUNT(*) FROM wdbc GROUP BY diagnosis").json()["rows"])
    assert counts == {"malignant": 212, "benign": 357}
    split = dict(_query(client, admin, "SELECT split, COUNT(*) FROM wdbc GROUP BY split").json()["rows"])
    assert split == {"train": 455, "test": 114}

    # Row 0 is WDBC ID 842302 (17.99, 10.38, 122.8, 1001 ...), a malignant case.
    row = _query(client, admin, "SELECT diagnosis, radius_mean, texture_mean, perimeter_mean, area_mean "
                                "FROM wdbc WHERE id = 0").json()["rows"][0]
    assert row == ["malignant", 17.99, 10.38, 122.8, 1001.0]

    # The dataset table reads in its natural order, the log tables newest first.
    page = client.get("/db/sql/tables/wdbc?limit=3", headers=admin).json()
    assert page["order"] == "asc" and [r[0] for r in page["rows"]] == [0, 1, 2]


def test_wdbc_test_rows_match_the_api_samples(client, admin):
    from conftest import SAMPLES

    rows = _query(client, admin, "SELECT sample_id, diagnosis, radius_mean, concave_points_worst "
                                 "FROM wdbc WHERE split = 'test'").json()["rows"]
    assert len(rows) == len(SAMPLES)
    for sample_id, diagnosis, radius, worst_cp in rows:
        sample = SAMPLES[sample_id]
        assert sample["label"] == diagnosis
        assert sample["features"]["mean radius"] == radius
        assert sample["features"]["worst concave points"] == worst_cp


def test_tables_show_username_not_user_id(client, admin, user, features):
    res = client.post("/db/predictions", headers=user["headers"], json={"items": [prediction_item(features)]})
    assert res.status_code == 201, res.text
    tables = {t["name"]: t for t in client.get("/db/sql/tables", headers=admin).json()["tables"]}
    assert tables["predictions"]["columns"][:2] == ["id", "username"]
    assert "user_id" not in tables["predictions"]["columns"]
    assert "password_hash" not in tables["users"]["columns"]

    rows = client.get("/db/sql/tables/predictions?limit=5", headers=admin).json()
    assert rows["order"] == "desc" and "user_id" not in rows["columns"]
    assert rows["rows"][0][1] == user["username"]
    users = client.get("/db/sql/tables/users", headers=admin).json()
    assert "password_hash" not in users["columns"]
    assert client.get("/db/sql/tables/not_a_table", headers=admin).status_code == 404


def test_password_hashes_never_leave_the_server(client, admin):
    assert _query(client, admin, "SELECT password_hash AS x FROM users").status_code == 400
    res = _query(client, admin, "SELECT * FROM users")
    assert res.status_code == 200, res.text
    assert all("$2b$" not in str(v) for row in res.json()["rows"] for v in row)


def test_results_are_capped_at_500_rows(client, admin):
    body = _query(client, admin, "SELECT id FROM wdbc").json()
    assert len(body["rows"]) == 500 and body["truncated"] is True
    body = _query(client, admin, "SELECT id FROM wdbc LIMIT 10").json()
    assert len(body["rows"]) == 10 and body["truncated"] is False


@pytest.mark.parametrize("sql", [
    "DELETE FROM wdbc",
    "UPDATE users SET username = 'x'",
    "DROP TABLE wdbc",
    "INSERT INTO wdbc (id) VALUES (9999)",
    "SELECT 1; DELETE FROM wdbc",
    "WITH x AS (SELECT 1) DELETE FROM wdbc",
    "WITH gone AS (DELETE FROM wdbc RETURNING id) SELECT * FROM gone",
    "PRAGMA query_only = OFF",
    "ATTACH DATABASE 'x.db' AS x",
])
def test_writes_are_rejected(client, admin, sql):
    before = _count(client, admin, "wdbc")
    res = _query(client, admin, sql)
    assert res.status_code == 400, res.text
    assert res.json()["detail"]
    assert _count(client, admin, "wdbc") == before


def test_sql_errors_are_reported_in_plain_words(client, admin):
    res = _query(client, admin, "SELECT no_such_column FROM wdbc")
    assert res.status_code == 400 and res.json()["detail"].startswith("Lỗi SQL:")
