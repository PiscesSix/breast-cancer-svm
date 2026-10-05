"""Model-API routes used by the dashboard: classes, dataset statistics, PCA, model comparison, the
test-set scores of the deployed model (for the interactive threshold analysis) and the permutation
importance of its features.

Every number returned here is computed from load_breast_cancer, the saved artifact or
reports/comparison.json; the web pages render them as-is and hard-code nothing.
"""

from __future__ import annotations

import threading
import time
from functools import lru_cache

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from sklearn.decomposition import PCA
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

import security
from app import comparison
from app.classes import CLASSES
from app.model_service import service
from scripts.train import load_data

router = APIRouter()
_state: dict = {"report": None, "error": None}
_train_lock = threading.Lock()

KEY_FEATURES = ["mean radius", "mean texture", "mean area", "mean concave points", "worst radius",
                "worst area", "worst concave points", "worst concavity"]
FEATURE_VI = {
    "radius": "bán kính", "texture": "kết cấu", "perimeter": "chu vi", "area": "diện tích",
    "smoothness": "độ trơn", "compactness": "độ đặc", "concavity": "độ lõm", "concave points": "số điểm lõm",
    "symmetry": "độ đối xứng", "fractal dimension": "chiều fractal",
}


def load_comparison() -> None:
    try:
        _state["report"], _state["error"] = comparison.load(), None
    except Exception as exc:  # noqa: BLE001 - reported by the endpoint as 503
        _state["report"], _state["error"] = None, f"Chưa có kết quả so sánh mô hình: {exc}"


def _vi(value: float, spec: str) -> str:
    """Vietnamese number format: comma as the decimal separator."""
    return format(value, spec).replace(".", ",")


def feature_vi(name: str) -> str:
    """'worst concave points' -> 'số điểm lõm (worst)'."""
    for group in ("mean ", "worst "):
        if name.startswith(group):
            return f"{FEATURE_VI[name.removeprefix(group)]} ({group.strip()})"
    return f"{FEATURE_VI[name.removesuffix(' error')]} (error)"


@router.get("/classes", tags=["Dữ liệu"])
def classes():
    """The two classes with a description and a credited cytology image."""
    return {"count": len(CLASSES), "classes": list(CLASSES.values())}


@lru_cache(maxsize=1)
def _summary() -> dict:
    X, y, names, _ = load_data()
    out = {}
    for key, info in CLASSES.items():
        rows = X[y == info["class_id"]]
        other = X[y != info["class_id"]]
        stats = {n: {"mean": round(float(rows[:, i].mean()), 4), "std": round(float(rows[:, i].std(ddof=1)), 4),
                     "min": round(float(rows[:, i].min()), 4), "max": round(float(rows[:, i].max()), 4)}
                 for i, n in enumerate(names)}
        # Largest standardised gap between the two classes: the features that separate them best.
        pooled = X.std(axis=0, ddof=1)
        gap = (rows.mean(axis=0) - other.mean(axis=0)) / pooled
        top = [names[i] for i in np.argsort(-np.abs(gap))[:4]]
        highlights = [
            f"{feature_vi(n).capitalize()} trung bình {_vi(stats[n]['mean'], '.4g')} — "
            f"{'cao hơn' if gap[names.index(n)] > 0 else 'thấp hơn'} nhóm còn lại "
            f"{_vi(abs(gap[names.index(n)]), '.2f')} độ lệch chuẩn."
            for n in top
        ]
        out[key] = {
            "key": key, "count": int(len(rows)), "share": round(len(rows) / len(y) * 100, 1),
            "stats": stats, "key_features": KEY_FEATURES, "top_features": top, "highlights": highlights,
            "n_zero_concavity": int(np.sum(rows[:, names.index("mean concavity")] == 0)),
        }
    return {"source": "sklearn.datasets.load_breast_cancer", "n_samples": int(len(y)), "n_features": len(names),
            "feature_names": names, "feature_vi": {n: feature_vi(n) for n in names}, "classes": out}


@lru_cache(maxsize=1)
def default_sample() -> dict:
    """Row 0 of the dataset: WDBC ID 842302 in the UCI / Kaggle file (sklearn keeps the same row order)."""
    X, y, names, target_names = load_data()
    return {"id": "WDBC 842302", "label": target_names[int(y[0])],
            "features": {n: float(v) for n, v in zip(names, X[0], strict=True)}}


@router.get("/dataset/summary", tags=["Dữ liệu"])
def dataset_summary():
    """Per-class statistics of the 30 features and the features that separate the classes best."""
    return _summary()


@lru_cache(maxsize=1)
def _pca() -> dict:
    X, y, _, _ = load_data()
    pca = PCA(n_components=2)
    coords = pca.fit_transform(StandardScaler().fit_transform(X))
    return {
        "n_samples": int(len(y)),
        "explained_variance_ratio": [round(float(r), 4) for r in pca.explained_variance_ratio_],
        "points": [{"label": "malignant" if t == 0 else "benign", "pc1": round(float(c[0]), 4),
                    "pc2": round(float(c[1]), 4)} for c, t in zip(coords, y, strict=True)],
    }


@router.get("/dataset/pca", tags=["Dữ liệu"])
def dataset_pca():
    """PCA 2D of the 569 standardised samples."""
    return _pca()


@router.get("/analysis/test-scores", tags=["Phân tích"])
def test_scores():
    """True label and P(malignant) of the deployed model for every test sample (threshold explorer)."""
    if not service.ready:
        raise HTTPException(503, service.error or "Mô hình chưa sẵn sàng")
    rows = [(s["id"], s["label"]) for s in service.samples]
    proba = [r["probability_malignant"] for r in service.predict([s["features"] for s in service.samples])]
    return {
        "threshold": service.threshold,
        "target_sensitivity": service.metadata["target_sensitivity"],
        "items": [{"id": i, "label": label, "proba_malignant": p} for (i, label), p in zip(rows, proba, strict=True)],
    }


PERMUTATION_REPEATS = 10


@lru_cache(maxsize=1)
def _permutation_importance(model_version: str) -> dict:
    names = service.metadata["feature_names"]
    class_id = {label: int(cid) for cid, label in service.metadata["class_mapping"].items()}
    X = np.array([[s["features"][n] for n in names] for s in service.samples], dtype=float)
    y = np.array([class_id[s["label"]] for s in service.samples])
    # ROC-AUC does not depend on the decision threshold, so the ranking is the same at any slider value.
    result = permutation_importance(service.model, X, y, scoring="roc_auc", n_repeats=PERMUTATION_REPEATS,
                                    random_state=42)
    baseline = roc_auc_score(y, service.model.predict_proba(X)[:, 1])
    order = np.argsort(-result.importances_mean)
    return {
        "model_version": model_version,
        "scoring": "roc_auc",
        "baseline_score": round(float(baseline), 4),
        "n_samples": int(len(y)),
        "n_repeats": PERMUTATION_REPEATS,
        "items": [{"feature": names[i], "feature_vi": feature_vi(names[i]),
                   "mean": round(float(result.importances_mean[i]), 5),
                   "std": round(float(result.importances_std[i]), 5)} for i in order],
    }


@router.get("/analysis/permutation-importance", tags=["Phân tích"])
def permutation_importance_endpoint():
    """Permutation importance of the 30 features on the test split (drop in ROC-AUC when one column is shuffled).

    SVC with an RBF kernel has neither coef_ nor feature_importances_, so importance is measured by
    shuffling each feature 10 times and recording how much the test ROC-AUC falls.
    """
    if not service.ready:
        raise HTTPException(503, service.error or "Mô hình chưa sẵn sàng")
    return _permutation_importance(service.metadata["model_version"])


def _require_report() -> dict:
    if _state["report"] is None:
        raise HTTPException(503, _state["error"] or "Chưa có kết quả so sánh mô hình")
    return _state["report"]


@router.get("/models/metrics", tags=["So sánh mô hình"])
def models_metrics():
    """Comparison table of the five classifiers from the latest training."""
    return _require_report()


@router.post("/models/train", tags=["So sánh mô hình"])
def models_train(user: dict = Depends(security.current_user)):
    """Retrain and re-evaluate the five classifiers (needs a JWT from the database API)."""
    if not _train_lock.acquire(blocking=False):
        raise HTTPException(409, "Đang có một lần train khác chạy, hãy thử lại sau ít giây")
    try:
        started = time.perf_counter()
        report = comparison.train_all(log=lambda *_: None)
        report["total_seconds"] = round(time.perf_counter() - started, 2)
        report["trained_by"] = user["username"]
        comparison.save(report)
        _state["report"], _state["error"] = report, None
        return report
    finally:
        _train_lock.release()
