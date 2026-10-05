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


def test_test_scores_reproduce_the_locked_metrics(client):
    """The threshold slider recomputes the test metrics in the browser from these scores; at the
    default (locked) threshold they must equal the metrics stored with the model."""
    body = client.get("/analysis/test-scores").json()
    meta = client.get("/metadata").json()
    assert body["threshold"] == meta["threshold_malignant"]
    t = body["threshold"]
    tp = sum(s["label"] == "malignant" and s["proba_malignant"] >= t for s in body["items"])
    fn = sum(s["label"] == "malignant" and s["proba_malignant"] < t for s in body["items"])
    tn = sum(s["label"] == "benign" and s["proba_malignant"] < t for s in body["items"])
    fp = sum(s["label"] == "benign" and s["proba_malignant"] >= t for s in body["items"])
    assert round(tp / (tp + fn), 4) == round(meta["test_metrics"]["sensitivity"], 4)
    assert round(tn / (tn + fp), 4) == round(meta["test_metrics"]["specificity"], 4)
    assert tp / (tp + fn) >= body["target_sensitivity"]


def test_wdbc_id_842302_is_malignant_at_the_default_threshold(client):
    from sklearn.datasets import load_breast_cancer

    data = load_breast_cancer()
    row = dict(zip(data.feature_names, data.data[0].tolist(), strict=True))
    first_four = ("mean radius", "mean texture", "mean perimeter", "mean area")
    assert [row[n] for n in first_four] == [17.99, 10.38, 122.8, 1001.0]
    body = client.post("/predict", json=row).json()
    assert body["predicted_label"] == "malignant"
    assert body["probability_malignant"] >= body["threshold_malignant"]
    assert body["inference_ms"] >= 0


def test_permutation_importance_ranks_all_30_features(client):
    body = client.get("/analysis/permutation-importance").json()
    names = client.get("/metadata").json()["feature_names"]
    assert body["scoring"] == "roc_auc" and body["n_samples"] == 114 and body["n_repeats"] == 10
    assert sorted(i["feature"] for i in body["items"]) == sorted(names)
    means = [i["mean"] for i in body["items"]]
    assert means == sorted(means, reverse=True) and means[0] > 0
    assert all(i["std"] >= 0 and i["feature_vi"] for i in body["items"])
    assert 0.5 < body["baseline_score"] <= 1


def test_dashboard_and_old_ui_address(client):
    html = client.get("/", headers={"Accept": "text/html"})
    assert html.status_code == 200 and "js/app.js" in html.text
    redirect = client.get("/ui?sample=malignant&auto=1", follow_redirects=False)
    assert redirect.status_code == 307 and redirect.headers["location"] == "/?sample=malignant&auto=1#/chan-doan"
    assert client.get("/config.js").status_code == 200


def test_default_sample_is_wdbc_842302(client):
    """The diagnosis form opens with this record; it must be predictable as-is and be malignant."""
    body = client.get("/samples/default").json()
    assert body["id"] == "WDBC 842302" and body["label"] == "malignant"
    assert len(body["features"]) == 30 and body["features"]["mean radius"] == 17.99
    pred = client.post("/predict", json=body["features"]).json()
    assert pred["predicted_label"] == "malignant"
