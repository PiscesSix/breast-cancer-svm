"""Train the breast cancer SVM, choose its probability calibration and decision threshold,
then export the artifacts served by the API.

Steps (every choice is made on the training set only; the test set is touched once, at the end):
  1. Load load_breast_cancer, check target_names, split 80/20 (stratify, random_state=42).
  2. GridSearchCV(StratifiedKFold 5) over C and gamma of Pipeline(StandardScaler, SVC rbf balanced).
  3. Compare three ways to get probabilities with out-of-fold predictions on the training set:
     SVC(probability=True) (the lecture's baseline, deprecated in scikit-learn 1.9) and three
     CalibratedClassifierCV variants. Keep the non-deprecated one with the lowest Brier score.
  4. On the same out-of-fold probabilities, pick the highest threshold on P(malignant) whose
     sensitivity is still >= the target (0.97 by default), then lock it.
  5. Refit on the whole training set, evaluate once on the test set, write the artifacts.

Run:  python scripts/train.py [--target-sensitivity 0.97]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
import time
import warnings
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.calibration import CalibratedClassifierCV
from sklearn.datasets import load_breast_cancer
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "artifacts"
REPORT_DIR = ROOT / "reports"
MODEL_PATH = ARTIFACT_DIR / "breast_cancer_svm.joblib"
METADATA_PATH = ARTIFACT_DIR / "metadata.json"
SAMPLES_PATH = ARTIFACT_DIR / "test_samples.json"
TRAIN_REPORT_PATH = REPORT_DIR / "train_report.json"

MODEL_NAME = "breast-cancer-svm-rbf"
MODEL_VERSION = "1.0.0"
RANDOM_STATE = 42
TEST_SIZE = 0.20
N_SPLITS = 5
DEFAULT_TARGET_SENSITIVITY = 0.97
UPPER_BOUND_FACTOR = 3.0
PARAM_GRID = {"svc__C": [0.1, 1, 10, 100], "svc__gamma": ["scale", 0.001, 0.01, 0.1]}
CLASS_MAPPING = {"0": "malignant", "1": "benign"}
MALIGNANT = 0
WARNING = (
    "Chỉ phục vụ mục đích giáo dục, không thay thế chẩn đoán y khoa. "
    "Educational use only; not a medical diagnosis."
)
DEPRECATED_METHODS = {"svc_probability"}
CALIBRATION_LABELS = {
    "svc_probability": "SVC(probability=True) — Platt nội bộ của libsvm (deprecated từ 1.9)",
    "calibrated_sigmoid_single": "CalibratedClassifierCV(method='sigmoid', ensemble=False)",
    "calibrated_sigmoid": "CalibratedClassifierCV(method='sigmoid')",
    "calibrated_isotonic": "CalibratedClassifierCV(method='isotonic')",
}


def load_data() -> tuple[np.ndarray, np.ndarray, list[str], list[str]]:
    """Return X, y, feature names and class names, refusing a dataset whose labels changed meaning."""
    bundle = load_breast_cancer()
    target_names = [str(n) for n in bundle.target_names]
    if target_names != [CLASS_MAPPING["0"], CLASS_MAPPING["1"]]:
        raise RuntimeError(f"target_names không như mong đợi: {target_names}")
    return bundle.data.astype(float), bundle.target.astype(int), [str(f) for f in bundle.feature_names], target_names


def split(X: np.ndarray, y: np.ndarray):
    return train_test_split(X, y, test_size=TEST_SIZE, stratify=y, random_state=RANDOM_STATE)


def cv_splitter() -> StratifiedKFold:
    return StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)


def base_pipeline(**svc_params) -> Pipeline:
    return Pipeline([
        ("scaler", StandardScaler()),
        ("svc", SVC(kernel="rbf", class_weight="balanced", random_state=RANDOM_STATE, **svc_params)),
    ])


def data_hash(X: np.ndarray, y: np.ndarray) -> str:
    digest = hashlib.sha256()
    digest.update(np.ascontiguousarray(X).tobytes())
    digest.update(np.ascontiguousarray(y).tobytes())
    return digest.hexdigest()


def malignant_proba(model, X: np.ndarray) -> np.ndarray:
    """P(malignant) whatever the column order of predict_proba."""
    return model.predict_proba(X)[:, list(model.classes_).index(MALIGNANT)]


def clinical_metrics(y_true: np.ndarray, proba: np.ndarray, threshold: float) -> dict:
    """Metrics with malignant (label 0) as the positive class; predicted malignant when proba >= threshold."""
    actual = y_true == MALIGNANT
    predicted = proba >= threshold
    tp = int(np.sum(actual & predicted))
    fn = int(np.sum(actual & ~predicted))
    fp = int(np.sum(~actual & predicted))
    tn = int(np.sum(~actual & ~predicted))
    sensitivity = tp / (tp + fn) if tp + fn else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    precision = tp / (tp + fp) if tp + fp else 0.0
    f1 = 2 * precision * sensitivity / (precision + sensitivity) if precision + sensitivity else 0.0
    return {
        "threshold": round(float(threshold), 6),
        "n": int(len(y_true)),
        "sensitivity": round(sensitivity, 4),
        "specificity": round(specificity, 4),
        "precision_malignant": round(precision, 4),
        "npv": round(tn / (tn + fn), 4) if tn + fn else 0.0,
        "f1_malignant": round(f1, 4),
        "accuracy": round((tp + tn) / len(y_true), 4),
        "roc_auc": round(float(roc_auc_score(actual.astype(int), proba)), 4),
        "pr_auc": round(float(average_precision_score(actual.astype(int), proba)), 4),
        "brier": round(float(brier_score_loss(actual.astype(int), proba)), 4),
        # Rows = actual [malignant, benign], columns = predicted [malignant, benign].
        "confusion_matrix": [[tp, fn], [fp, tn]],
        "false_negatives": fn,
        "false_positives": fp,
    }


def choose_threshold(y_true: np.ndarray, proba: np.ndarray, target: float) -> float:
    """Highest threshold on P(malignant) that keeps sensitivity >= target (so specificity is as high as possible)."""
    malignant_scores = np.sort(proba[y_true == MALIGNANT])[::-1]
    chosen = float(malignant_scores[-1])
    for t in malignant_scores:
        if np.mean(proba[y_true == MALIGNANT] >= t) >= target:
            chosen = float(t)
            break
    # Round down to 4 decimals: the value shown in the API is then exactly the one applied,
    # and a lower threshold can only keep or raise sensitivity.
    return math.floor(chosen * 10_000) / 10_000


def calibration_candidates(svc_params: dict) -> dict:
    return {
        "svc_probability": base_pipeline(probability=True, **svc_params),
        # scikit-learn's documented replacement for SVC(probability=True).
        "calibrated_sigmoid_single": CalibratedClassifierCV(
            base_pipeline(**svc_params), method="sigmoid", cv=cv_splitter(), ensemble=False),
        "calibrated_sigmoid": CalibratedClassifierCV(base_pipeline(**svc_params), method="sigmoid", cv=cv_splitter()),
        "calibrated_isotonic": CalibratedClassifierCV(base_pipeline(**svc_params), method="isotonic", cv=cv_splitter()),
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Huấn luyện SVM chẩn đoán ung thư vú")
    parser.add_argument("--target-sensitivity", type=float, default=DEFAULT_TARGET_SENSITIVITY)
    args = parser.parse_args()
    started = time.perf_counter()

    X, y, feature_names, target_names = load_data()
    X_train, X_test, y_train, y_test = split(X, y)
    print(f"[data] {X.shape[0]} mẫu, {X.shape[1]} đặc trưng; nhãn {dict(enumerate(target_names))}")
    print(f"[data] ác tính {int(np.sum(y == 0))} / lành tính {int(np.sum(y == 1))}; "
          f"train {len(y_train)} / test {len(y_test)} (stratify, random_state={RANDOM_STATE})")

    # 1. Hyper-parameters, chosen by cross-validation on the training set only.
    search = GridSearchCV(base_pipeline(), PARAM_GRID, scoring="recall_macro", cv=cv_splitter(), n_jobs=-1, refit=True)
    t0 = time.perf_counter()
    search.fit(X_train, y_train)
    search_seconds = time.perf_counter() - t0
    best_idx = int(search.best_index_)
    cv_mean = float(search.cv_results_["mean_test_score"][best_idx])
    cv_std = float(search.cv_results_["std_test_score"][best_idx])
    svc_params = {k.removeprefix("svc__"): v for k, v in search.best_params_.items()}
    print(f"[grid] {len(search.cv_results_['params'])} cấu hình trong {search_seconds:.1f}s; "
          f"tốt nhất {search.best_params_} — recall_macro CV {cv_mean:.4f} ± {cv_std:.4f}")
    grid_rows = [
        {"C": p["svc__C"], "gamma": p["svc__gamma"], "mean": round(float(m), 4), "std": round(float(s), 4),
         "rank": int(r)}
        for p, m, s, r in zip(search.cv_results_["params"], search.cv_results_["mean_test_score"],
                              search.cv_results_["std_test_score"], search.cv_results_["rank_test_score"], strict=True)
    ]

    # 2. Probability calibration, compared on out-of-fold probabilities of the training set.
    calibration = []
    oof = {}
    for key, estimator in calibration_candidates(svc_params).items():
        with warnings.catch_warnings():
            # SVC(probability=True) is deprecated in scikit-learn 1.9; it stays here only as the lecture's baseline.
            warnings.simplefilter("ignore", FutureWarning)
            proba = cross_val_predict(estimator, X_train, y_train, cv=cv_splitter(),
                                      method="predict_proba")[:, MALIGNANT]
        oof[key] = proba
        actual = (y_train == MALIGNANT).astype(int)
        row = {
            "method": key,
            "label": CALIBRATION_LABELS[key],
            "brier": round(float(brier_score_loss(actual, proba)), 5),
            "log_loss": round(float(log_loss(actual, proba)), 5),
            "roc_auc": round(float(roc_auc_score(actual, proba)), 5),
            "deprecated": key in DEPRECATED_METHODS,
        }
        calibration.append(row)
        print(f"[calib] {key:<26} Brier {row['brier']:.5f}  log-loss {row['log_loss']:.5f}  "
              f"ROC-AUC {row['roc_auc']:.5f}")
    # A deprecated method would tie the artifact to scikit-learn < 1.11, so it only serves as a baseline.
    chosen = min((r for r in calibration if not r["deprecated"]), key=lambda r: r["brier"])["method"]
    print(f"[calib] chọn {chosen} (Brier nhỏ nhất trong các cách không bị deprecated, xác suất out-of-fold)")

    # 3. Decision threshold, chosen on the same out-of-fold probabilities and then locked.
    threshold = choose_threshold(y_train, oof[chosen], args.target_sensitivity)
    cv_at_threshold = clinical_metrics(y_train, oof[chosen], threshold)
    cv_at_half = clinical_metrics(y_train, oof[chosen], 0.5)
    print(f"[threshold] ngưỡng P(ác tính) = {threshold:.4f} để sensitivity ≥ {args.target_sensitivity:.2f} "
          f"(OOF: sensitivity {cv_at_threshold['sensitivity']:.4f}, specificity {cv_at_threshold['specificity']:.4f})")

    # 4. Refit on the whole training set and evaluate once on the untouched test set.
    model = calibration_candidates(svc_params)[chosen]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        model.fit(X_train, y_train)
    train_metrics = clinical_metrics(y_train, malignant_proba(model, X_train), threshold)
    test_proba = malignant_proba(model, X_test)
    test_metrics = clinical_metrics(y_test, test_proba, threshold)
    test_at_half = clinical_metrics(y_test, test_proba, 0.5)
    for name, m in (("train", train_metrics), ("cv (OOF)", cv_at_threshold), ("test", test_metrics)):
        print(f"[eval] {name:<9} sensitivity {m['sensitivity']:.4f}  specificity {m['specificity']:.4f}  "
              f"precision {m['precision_malignant']:.4f}  ROC-AUC {m['roc_auc']:.4f}  FN {m['false_negatives']}")

    # 5. Artifacts.
    ARTIFACT_DIR.mkdir(exist_ok=True)
    REPORT_DIR.mkdir(exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    train_min, train_max = X_train.min(axis=0), X_train.max(axis=0)
    features = [
        {
            "name": name,
            # Six concavity features are exactly 0 in 13 real samples, so only they allow 0.
            "allow_zero": bool(np.any(X == 0, axis=0)[i]),
            "train_min": round(float(train_min[i]), 6),
            "train_max": round(float(train_max[i]), 6),
            "upper_bound": round(float(train_max[i] * UPPER_BOUND_FACTOR), 6),
        }
        for i, name in enumerate(feature_names)
    ]
    metadata = {
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "feature_names": feature_names,
        "features": features,
        "class_mapping": CLASS_MAPPING,
        "positive_class": "malignant",
        "threshold_malignant": round(threshold, 6),
        "target_sensitivity": args.target_sensitivity,
        "decision_rule": "malignant if P(malignant) >= threshold_malignant, otherwise benign",
        "calibration": chosen,
        "best_params": search.best_params_,
        "cv_recall_macro": {"mean": round(cv_mean, 4), "std": round(cv_std, 4)},
        "test_metrics": {k: test_metrics[k] for k in ("sensitivity", "specificity", "precision_malignant",
                                                       "f1_malignant", "roc_auc", "pr_auc", "accuracy")},
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
        "train_date": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "data_hash": data_hash(X, y),
        "sklearn_version": sklearn.__version__,
        "numpy_version": np.__version__,
        "python_version": platform.python_version(),
        "random_state": RANDOM_STATE,
        "warning": WARNING,
    }
    METADATA_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    # Test rows with their true label, so the demo (/samples) never needs 30 numbers typed by hand.
    samples = [
        {"id": f"test-{i:03d}", "label": CLASS_MAPPING[str(int(label))],
         "features": {name: float(v) for name, v in zip(feature_names, row, strict=True)}}
        for i, (row, label) in enumerate(zip(X_test, y_test, strict=True))
    ]
    SAMPLES_PATH.write_text(json.dumps(samples, ensure_ascii=False), encoding="utf-8")

    report = {
        "generated_at": metadata["train_date"],
        "environment": {"python": platform.python_version(), "scikit_learn": sklearn.__version__,
                        "numpy": np.__version__},
        "data": {"n_samples": int(len(y)), "n_features": int(X.shape[1]), "n_malignant": int(np.sum(y == 0)),
                 "n_benign": int(np.sum(y == 1)), "n_train": int(len(y_train)), "n_test": int(len(y_test)),
                 "test_malignant": int(np.sum(y_test == 0)), "test_benign": int(np.sum(y_test == 1)),
                 "n_zero_rows": int(np.any(X == 0, axis=1).sum()),
                 "zero_features": [f["name"] for f in features if f["allow_zero"]]},
        "grid_search": {"scoring": "recall_macro", "n_configs": len(grid_rows), "seconds": round(search_seconds, 2),
                        "best_params": search.best_params_, "cv_mean": round(cv_mean, 4), "cv_std": round(cv_std, 4),
                        "results": grid_rows},
        "calibration": {"chosen": chosen,
                        "criterion": "Brier score thấp nhất trên xác suất out-of-fold của tập train, "
                                     "loại cách đã deprecated",
                        "candidates": calibration},
        "threshold": {"value": round(threshold, 6), "target_sensitivity": args.target_sensitivity,
                      "rule": "ngưỡng cao nhất trên P(ác tính) vẫn giữ sensitivity out-of-fold ≥ mục tiêu"},
        "metrics": {"train": train_metrics, "cv_oof": cv_at_threshold, "cv_oof_at_0_5": cv_at_half,
                    "test": test_metrics, "test_at_0_5": test_at_half},
        "oof": {"y_true": y_train.tolist(), "proba_malignant": [round(float(p), 6) for p in oof[chosen]]},
        "seconds": round(time.perf_counter() - started, 2),
    }
    TRAIN_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[save] {MODEL_PATH.relative_to(ROOT)}, {METADATA_PATH.relative_to(ROOT)}, "
          f"{SAMPLES_PATH.relative_to(ROOT)}, {TRAIN_REPORT_PATH.relative_to(ROOT)}")
    print(f"Đã lưu mô hình {MODEL_NAME} v{MODEL_VERSION} sau {report['seconds']:.1f}s.")


if __name__ == "__main__":
    main()
