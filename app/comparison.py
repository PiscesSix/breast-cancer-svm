"""Compare five classifiers under the same protocol as the deployed SVM.

For every model: GridSearchCV (StratifiedKFold 5, recall_macro) on the training split only,
probabilities (SVMs wrapped in CalibratedClassifierCV), a threshold on P(malignant) chosen on
out-of-fold probabilities for sensitivity >= target, then one evaluation on the test split and
timings measured with time.perf_counter. The best model is the one with the highest CV score.
"""

from __future__ import annotations

import json
import time
import warnings
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_curve
from sklearn.model_selection import GridSearchCV, cross_val_predict
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from scripts.train import (
    DEFAULT_TARGET_SENSITIVITY,
    MALIGNANT,
    PARAM_GRID,
    RANDOM_STATE,
    base_pipeline,
    choose_threshold,
    clinical_metrics,
    cv_splitter,
    load_data,
    split,
)

REPORT_PATH = Path(__file__).resolve().parents[1] / "reports" / "comparison.json"
PREDICT_REPEATS = 200
SPEED_THRESHOLDS = {"fast": 1.5, "medium": 3.0}
MODEL_KEYS = ["svm_rbf", "svm_linear", "logreg", "knn", "random_forest"]
LABELS = {
    "svm_rbf": "SVM (RBF)",
    "svm_linear": "SVM tuyến tính",
    "logreg": "Logistic Regression",
    "knn": "K láng giềng gần (KNN)",
    "random_forest": "Random Forest",
}


def candidates() -> dict:
    """(estimator, parameter grid, wrap in a probability calibrator?) for each model."""
    return {
        "svm_rbf": (base_pipeline(), PARAM_GRID, True),
        "svm_linear": (
            Pipeline([("scaler", StandardScaler()),
                      ("svc", SVC(kernel="linear", class_weight="balanced", random_state=RANDOM_STATE))]),
            {"svc__C": [0.01, 0.1, 1, 10]}, True),
        "logreg": (
            Pipeline([("scaler", StandardScaler()),
                      ("clf", LogisticRegression(class_weight="balanced", max_iter=5000))]),
            {"clf__C": [0.01, 0.1, 1, 10, 100]}, False),
        "knn": (
            Pipeline([("scaler", StandardScaler()), ("clf", KNeighborsClassifier())]),
            {"clf__n_neighbors": [3, 5, 7, 9, 11, 15], "clf__weights": ["uniform", "distance"]}, False),
        "random_forest": (
            RandomForestClassifier(class_weight="balanced", random_state=RANDOM_STATE),
            {"n_estimators": [100, 300], "max_depth": [None, 5, 10]}, False),
    }


def _probabilistic(estimator, calibrate: bool):
    if calibrate:
        return CalibratedClassifierCV(estimator, method="sigmoid", cv=cv_splitter(), ensemble=False)
    return clone(estimator)


def _speed(value: float, fastest: float) -> dict:
    ratio = value / fastest if fastest else 1.0
    if ratio <= SPEED_THRESHOLDS["fast"]:
        tier, label = "fast", "Nhanh"
    elif ratio <= SPEED_THRESHOLDS["medium"]:
        tier, label = "medium", "Trung bình"
    else:
        tier, label = "slow", "Chậm"
    return {"tier": tier, "label": label, "ratio_to_fastest": round(ratio, 2)}


def _roc_points(y_true, proba, n: int = 60) -> dict:
    fpr, tpr, _ = roc_curve((y_true == MALIGNANT).astype(int), proba)
    idx = np.unique(np.linspace(0, len(fpr) - 1, min(n, len(fpr))).round().astype(int))
    return {"fpr": [round(float(v), 4) for v in fpr[idx]], "tpr": [round(float(v), 4) for v in tpr[idx]]}


def train_all(target_sensitivity: float = DEFAULT_TARGET_SENSITIVITY, log=print) -> dict:
    started = time.perf_counter()
    X, y, _, _ = load_data()
    X_train, X_test, y_train, y_test = split(X, y)
    rows = []
    for key, (estimator, grid, calibrate) in candidates().items():
        search = GridSearchCV(estimator, grid, scoring="recall_macro", cv=cv_splitter(), n_jobs=-1)
        search.fit(X_train, y_train)
        i = int(search.best_index_)
        best = search.best_estimator_

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            oof = cross_val_predict(_probabilistic(best, calibrate), X_train, y_train, cv=cv_splitter(),
                                    method="predict_proba")[:, MALIGNANT]
        threshold = choose_threshold(y_train, oof, target_sensitivity)

        model = _probabilistic(best, calibrate)
        t0 = time.perf_counter()
        model.fit(X_train, y_train)
        train_seconds = time.perf_counter() - t0
        col = list(model.classes_).index(MALIGNANT)
        proba = model.predict_proba(X_test)[:, col]
        t0 = time.perf_counter()
        for _ in range(PREDICT_REPEATS):
            model.predict_proba(X_test)
        predict_ms = (time.perf_counter() - t0) * 1000 / (PREDICT_REPEATS * len(X_test))

        m = clinical_metrics(y_test, proba, threshold)
        rows.append({
            "model": key,
            "label": LABELS[key],
            "best_params": {k.split("__")[-1]: v for k, v in search.best_params_.items()},
            "cv_mean": round(float(search.cv_results_["mean_test_score"][i]), 4),
            "cv_std": round(float(search.cv_results_["std_test_score"][i]), 4),
            "n_configs": len(search.cv_results_["params"]),
            **{k: m[k] for k in ("threshold", "sensitivity", "specificity", "precision_malignant", "f1_malignant",
                                 "roc_auc", "pr_auc", "brier", "accuracy", "false_negatives", "false_positives",
                                 "confusion_matrix")},
            "train_seconds": round(train_seconds, 4),
            "predict_ms_per_sample": round(predict_ms, 5),
            "roc": _roc_points(y_test, proba),
        })
        log(f"[compare] {LABELS[key]:<24} CV {rows[-1]['cv_mean']:.4f}  sens {m['sensitivity']:.4f}  "
            f"spec {m['specificity']:.4f}  AUC {m['roc_auc']:.4f}  train {train_seconds * 1000:.1f} ms")

    fastest_train = min(r["train_seconds"] for r in rows)
    fastest_predict = min(r["predict_ms_per_sample"] for r in rows)
    for r in rows:
        r["train_speed"] = _speed(r["train_seconds"], fastest_train)
        r["predict_speed"] = _speed(r["predict_ms_per_sample"], fastest_predict)
    best = max(rows, key=lambda r: (r["cv_mean"], r["roc_auc"]))
    return {
        "trained_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "task": {"type": "classification", "positive_class": "malignant", "selection": "CV recall_macro"},
        "data": {"n_samples": int(len(y)), "train_size": int(len(y_train)), "test_size": int(len(y_test)),
                 "cv": "StratifiedKFold(n_splits=5, shuffle=True, random_state=42)"},
        "target_sensitivity": target_sensitivity,
        "speed_thresholds": SPEED_THRESHOLDS,
        "best_model": best["model"],
        "models": rows,
        "total_seconds": round(time.perf_counter() - started, 2),
    }


def save(report: dict, path: Path = REPORT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def load(path: Path = REPORT_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
