"""API test matrix of the lecture (slide 26): happy path, missing / extra fields, wrong types,
invalid values, availability — plus the batch, samples and 503 paths added in this project."""

from __future__ import annotations

import json
import logging

import pytest

from app.model_service import service

FEATURE_COUNT = 30


# ---------------------------------------------------------------- availability

def test_health_reports_loaded_model(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["model_loaded"] is True
    assert body["model_version"] == service.metadata["model_version"]


def test_root_is_json_for_api_clients_and_html_for_browsers(client):
    body = client.get("/").json()
    assert body["docs"] == "/docs" and "giáo dục" in body["warning"]
    html = client.get("/", headers={"Accept": "text/html"})
    assert html.status_code == 200 and "text/html" in html.headers["content-type"]
    assert client.get("/ui").status_code == 200


def test_metadata_has_30_features_threshold_and_warning(client):
    r = client.get("/metadata")
    assert r.status_code == 200
    meta = r.json()
    assert len(meta["feature_names"]) == FEATURE_COUNT
    assert meta["class_mapping"] == {"0": "malignant", "1": "benign"}
    assert 0 < meta["threshold_malignant"] < 1
    assert meta["warning"] and meta["model_version"]


def test_every_response_carries_a_request_id(client):
    assert client.get("/health").headers.get("x-request-id")
    assert client.get("/health", headers={"X-Request-ID": "abc123"}).headers["x-request-id"] == "abc123"


# ---------------------------------------------------------------- happy path

def test_predict_flat_and_wrapped_payloads_agree(client, features):
    flat = client.post("/predict", json=features)
    wrapped = client.post("/predict", json={"features": features})
    assert flat.status_code == wrapped.status_code == 200
    a, b = flat.json(), wrapped.json()
    assert a.pop("inference_ms") >= 0 and b.pop("inference_ms") >= 0  # timing differs per call
    assert a == b


def test_prediction_label_follows_the_threshold(client, features):
    body = client.post("/predict", json=features).json()
    assert abs(body["probability_malignant"] + body["probability_benign"] - 1) < 1e-3
    expected = "malignant" if body["probability_malignant"] >= body["threshold_malignant"] else "benign"
    assert body["predicted_label"] == expected
    assert body["predicted_class"] == (0 if expected == "malignant" else 1)
    assert body["model_version"] == service.metadata["model_version"] and body["warning"]


def test_zero_is_accepted_where_the_dataset_has_zeros(client, features):
    features["mean concavity"] = 0
    features["mean concave points"] = 0
    assert client.post("/predict", json=features).status_code == 200


# ---------------------------------------------------------------- missing / extra fields

def test_missing_feature_returns_422_with_its_name(client, features):
    features.pop("mean radius")
    r = client.post("/predict", json=features)
    assert r.status_code == 422
    assert r.json()["missing"] == ["mean radius"]


def test_lecture_payload_with_one_feature_lists_the_other_29(client):
    r = client.post("/predict", json={"features": {"mean radius": 10.0}})
    assert r.status_code == 422
    assert len(r.json()["missing"]) == FEATURE_COUNT - 1


def test_extra_feature_returns_422_with_its_name(client, features):
    features["patient_name"] = 1.0
    r = client.post("/predict", json=features)
    assert r.status_code == 422
    assert r.json()["extra"] == ["patient_name"]


def test_empty_body_is_rejected(client):
    assert client.post("/predict", json={}).status_code == 422


# ---------------------------------------------------------------- wrong types and invalid values

@pytest.mark.parametrize("bad", ["12.5", None, [1.0], {"v": 1.0}, True])
def test_wrong_type_returns_422(client, features, bad):
    features["mean area"] = bad
    assert client.post("/predict", json=features).status_code == 422


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_numbers_return_422(client, features, literal):
    # json.dumps cannot emit NaN here, so the literal is written into the raw body.
    features["mean area"] = 123456.789
    raw = json.dumps(features).replace("123456.789", literal)
    r = client.post("/predict", content=raw, headers={"Content-Type": "application/json"})
    assert r.status_code == 422


@pytest.mark.parametrize("value", [0, -1.0])
def test_non_positive_value_on_a_positive_feature_returns_422(client, features, value):
    features["mean radius"] = value
    assert client.post("/predict", json=features).status_code == 422


def test_value_far_outside_the_training_range_returns_422(client, features):
    features["mean area"] = 1e6
    r = client.post("/predict", json=features)
    assert r.status_code == 422
    assert r.json()["detail"]["out_of_range"][0]["feature"] == "mean area"


def test_malformed_json_returns_422(client):
    r = client.post("/predict", content="{not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422


# ---------------------------------------------------------------- batch

def test_batch_predicts_each_record(client, features):
    r = client.post("/predict/batch", json={"items": [features, {"features": features}]})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2 and len(body["results"]) == 2
    assert body["results"][0] == body["results"][1]


@pytest.mark.parametrize("size", [0, 101])
def test_batch_size_is_limited_to_1_to_100(client, features, size):
    assert client.post("/predict/batch", json={"items": [features] * size}).status_code == 422


def test_batch_rejects_the_whole_request_if_one_record_is_invalid(client, features):
    broken = dict(features)
    broken.pop("worst area")
    assert client.post("/predict/batch", json={"items": [features, broken]}).status_code == 422


# ---------------------------------------------------------------- samples

def test_samples_filter_by_true_label(client):
    body = client.get("/samples", params={"n": 5, "label": "benign"}).json()
    assert body["count"] == 5
    assert {item["label"] for item in body["items"]} == {"benign"}
    assert all(len(item["features"]) == FEATURE_COUNT for item in body["items"])


def test_samples_are_reproducible_with_a_seed(client):
    a = client.get("/samples", params={"n": 3, "seed": 7}).json()
    b = client.get("/samples", params={"n": 3, "seed": 7}).json()
    assert [i["id"] for i in a["items"]] == [i["id"] for i in b["items"]]


def test_samples_validate_their_parameters(client):
    assert client.get("/samples", params={"label": "unknown"}).status_code == 422
    assert client.get("/samples", params={"n": 0}).status_code == 422


def test_sample_payload_can_be_sent_back_to_predict(client):
    item = client.get("/samples", params={"n": 1, "label": "malignant", "seed": 1}).json()["items"][0]
    assert client.post("/predict", json={"features": item["features"]}).status_code == 200


# ---------------------------------------------------------------- privacy and failure modes

def test_payload_values_never_reach_the_log(client, features, caplog):
    features["mean area"] = 1234.5678
    with caplog.at_level(logging.INFO, logger="breast_cancer_api"):
        client.post("/predict", json=features)
        features["mean area"] = "not a number"
        client.post("/predict", json=features)
    assert "1234.5678" not in caplog.text and "not a number" not in caplog.text
    assert "prediction=" in caplog.text


def test_missing_artifact_gives_503(client, monkeypatch):
    monkeypatch.setattr(service, "model", None)
    monkeypatch.setattr(service, "error", "artifact missing (test)")
    assert client.get("/health").status_code == 503
    assert client.post("/predict", json={"features": {}}).status_code in (422, 503)
    assert client.get("/metadata").status_code == 503
