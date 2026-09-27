"""Prediction history: stored per user, filtered, confirmed labels, isolation between users."""

from __future__ import annotations

from conftest import new_user, prediction_item


def test_save_and_list_own_predictions(client, user, features):
    res = client.post("/db/predictions", json={"items": [prediction_item(features)]}, headers=user["headers"])
    assert res.status_code == 201
    body = client.get("/db/predictions", headers=user["headers"]).json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["predicted_label"] == "malignant" and item["correct"] is True
    assert item["input"]["mean radius"] == features["mean radius"]


def test_users_only_see_their_own_history(client, features):
    alice, bob = new_user(client, "alice"), new_user(client, "bob")
    client.post("/db/predictions", json={"items": [prediction_item(features)]}, headers=alice["headers"])
    assert client.get("/db/predictions", headers=bob["headers"]).json()["total"] == 0
    row_id = client.get("/db/predictions", headers=alice["headers"]).json()["items"][0]["id"]
    res = client.patch(f"/db/predictions/{row_id}", json={"actual_label": "benign"}, headers=bob["headers"])
    assert res.status_code == 404


def test_confirmed_label_updates_correctness(client, user, features):
    client.post("/db/predictions", json={"items": [prediction_item(features, actual=None)]}, headers=user["headers"])
    row = client.get("/db/predictions", headers=user["headers"]).json()["items"][0]
    assert row["correct"] is None
    updated = client.patch(f"/db/predictions/{row['id']}", json={"actual_label": "benign"}, headers=user["headers"])
    assert updated.status_code == 200 and updated.json()["correct"] is False


def test_invalid_labels_and_anonymous_access_are_rejected(client, user, features):
    bad = prediction_item(features, label="unknown")
    assert client.post("/db/predictions", json={"items": [bad]}, headers=user["headers"]).status_code == 422
    assert client.get("/db/predictions").status_code == 401


def test_filter_by_model(client, user, features):
    items = [prediction_item(features), {**prediction_item(features), "model": "logreg"}]
    client.post("/db/predictions", json={"items": items}, headers=user["headers"])
    body = client.get("/db/predictions", params={"model": "logreg"}, headers=user["headers"]).json()
    assert body["total"] == 1 and body["items"][0]["model"] == "logreg"
