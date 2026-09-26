"""Model regression tests: the saved artifact must reproduce the same data split, the same fixed
predictions and at least the minimum clinical quality stated in metadata.json."""

from __future__ import annotations

import pytest

from app.model_service import service
from conftest import SAMPLES
from scripts.train import clinical_metrics, data_hash, load_data, malignant_proba, split

MIN_TEST_SENSITIVITY = 0.95
MIN_TEST_ROC_AUC = 0.98

# Fixed records of the test split -> (expected label, P(malignant) recorded when the artifact was built).
REFERENCE = {
    "test-000": ("malignant", 1.0),
    "test-001": ("benign", 0.0001),
    "test-002": ("malignant", 0.9871),
    "test-053": ("benign", 0.0987),   # the one malignant case the model misses (a known false negative)
    "test-016": ("malignant", 0.7249),  # a benign case flagged as malignant (a known false positive)
}


@pytest.fixture(scope="module")
def data():
    X, y, _, _ = load_data()
    return X, y, split(X, y)


def test_dataset_is_the_one_the_artifact_was_trained_on(client, data):
    X, y, _ = data
    assert data_hash(X, y) == service.metadata["data_hash"]


def test_saved_samples_are_the_test_split(client, data):
    _, _, (_, X_test, _, y_test) = data
    assert len(SAMPLES) == len(y_test) == service.metadata["n_test"]


@pytest.mark.parametrize("sample_id", list(REFERENCE))
def test_fixed_records_keep_their_prediction(client, sample_id):
    expected_label, expected_p = REFERENCE[sample_id]
    result = service.predict([SAMPLES[sample_id]["features"]])[0]
    assert result["predicted_label"] == expected_label
    assert result["probability_malignant"] == pytest.approx(expected_p, abs=1e-3)
    assert result["model_version"] == "1.0.0"


def test_test_metrics_match_metadata_and_minimum_quality(client, data):
    _, _, (_, X_test, _, y_test) = data
    m = clinical_metrics(y_test, malignant_proba(service.model, X_test), service.threshold)
    saved = service.metadata["test_metrics"]
    assert m["sensitivity"] == saved["sensitivity"] and m["specificity"] == saved["specificity"]
    assert m["sensitivity"] >= MIN_TEST_SENSITIVITY
    assert m["roc_auc"] >= MIN_TEST_ROC_AUC


def test_threshold_meets_the_target_on_out_of_fold_probabilities():
    import json

    from scripts.train import TRAIN_REPORT_PATH

    report = json.loads(TRAIN_REPORT_PATH.read_text(encoding="utf-8"))
    assert report["metrics"]["cv_oof"]["sensitivity"] >= report["threshold"]["target_sensitivity"]
