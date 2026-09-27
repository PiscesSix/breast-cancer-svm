"""Dashboard routes: classes and images, dataset statistics, PCA, model comparison, test scores."""

from __future__ import annotations

from app.comparison import MODEL_KEYS


def test_classes_have_credited_local_images(client):
    body = client.get("/classes").json()
    assert {c["key"] for c in body["classes"]} == {"malignant", "benign"}
    for c in body["classes"]:
        assert c["license"] and c["author"] and c["source_url"].startswith("https://commons.wikimedia.org/")
        assert client.get(c["image_url"]).status_code == 200


def test_dataset_summary_counts(client):
    body = client.get("/dataset/summary").json()
    assert body["n_samples"] == 569 and body["n_features"] == 30
    assert body["classes"]["malignant"]["count"] == 212 and body["classes"]["benign"]["count"] == 357
    assert len(body["classes"]["malignant"]["highlights"]) == 4


def test_pca_projects_every_sample(client):
    body = client.get("/dataset/pca").json()
    assert len(body["points"]) == 569
    r1, r2 = body["explained_variance_ratio"]
    assert r1 >= r2 > 0 and r1 + r2 < 1


def test_model_comparison_has_five_classifiers(client):
    body = client.get("/models/metrics").json()
    assert [m["model"] for m in body["models"]] == MODEL_KEYS
    for m in body["models"]:
        for key in ("sensitivity", "specificity", "roc_auc", "cv_mean", "threshold", "train_seconds",
                    "predict_ms_per_sample", "train_speed", "predict_speed", "roc"):
            assert key in m
        assert m["predict_speed"]["label"] in ("Nhanh", "Trung bình", "Chậm")
    assert body["best_model"] in MODEL_KEYS


def test_comparison_svm_row_matches_the_deployed_model(client):
    svm = next(m for m in client.get("/models/metrics").json()["models"] if m["model"] == "svm_rbf")
    meta = client.get("/metadata").json()
    assert svm["threshold"] == meta["threshold_malignant"]
    assert svm["sensitivity"] == meta["test_metrics"]["sensitivity"]


def test_test_scores_cover_the_test_split(client):
    body = client.get("/analysis/test-scores").json()
    assert len(body["items"]) == 114
    assert all(0 <= s["proba_malignant"] <= 1 for s in body["items"])


def test_dashboard_and_old_ui_address(client):
    html = client.get("/", headers={"Accept": "text/html"})
    assert html.status_code == 200 and "js/app.js" in html.text
    redirect = client.get("/ui?sample=malignant&auto=1", follow_redirects=False)
    assert redirect.status_code == 307 and redirect.headers["location"] == "/?sample=malignant&auto=1#/chan-doan"
    assert client.get("/config.js").status_code == 200
