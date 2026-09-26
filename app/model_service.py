"""Load the trained artifact once and turn validated features into a prediction.

The label always comes from the locked threshold on P(malignant), never from model.predict(),
so the returned label and probabilities can never contradict each other.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import joblib
import numpy as np
import sklearn

from app.schemas import FEATURE_ALIASES

BASE_DIR = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = BASE_DIR / "artifacts"
MODEL_PATH = ARTIFACT_DIR / "breast_cancer_svm.joblib"
METADATA_PATH = ARTIFACT_DIR / "metadata.json"
SAMPLES_PATH = ARTIFACT_DIR / "test_samples.json"

MALIGNANT = 0
LABEL_VI = {"malignant": "Ác tính", "benign": "Lành tính"}


class ArtifactError(RuntimeError):
    """The artifact is missing or does not match the API's schema."""


class OutOfRange(ValueError):
    """Some values exceed the plausible range learnt from the training data."""

    def __init__(self, fields: list[dict]):
        super().__init__("out of range")
        self.fields = fields


class ModelService:
    def __init__(self, model_path: Path = MODEL_PATH, metadata_path: Path = METADATA_PATH,
                 samples_path: Path = SAMPLES_PATH):
        self.model_path = model_path
        self.metadata_path = metadata_path
        self.samples_path = samples_path
        self.model = None
        self.metadata: dict = {}
        self.samples: list[dict] = []
        self.error: str | None = None

    @property
    def ready(self) -> bool:
        return self.model is not None

    def load(self) -> None:
        """Load model, metadata and demo samples; keep the error message instead of crashing."""
        try:
            metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            if metadata["feature_names"] != FEATURE_ALIASES:
                raise ArtifactError("feature_names trong metadata.json không khớp schema của API")
            if metadata["sklearn_version"] != sklearn.__version__:
                raise ArtifactError(
                    f"Artifact huấn luyện bằng scikit-learn {metadata['sklearn_version']}, "
                    f"môi trường đang chạy {sklearn.__version__}")
            model = joblib.load(self.model_path)
            samples = json.loads(self.samples_path.read_text(encoding="utf-8")) if self.samples_path.exists() else []
        except Exception as exc:  # noqa: BLE001 - reported through /health as 503
            self.model, self.error = None, f"Không nạp được artifact: {exc}"
            return
        self.model, self.metadata, self.samples, self.error = model, metadata, samples, None
        self._upper = {f["name"]: f["upper_bound"] for f in metadata["features"]}
        self._proba_col = list(model.classes_).index(MALIGNANT)

    @property
    def threshold(self) -> float:
        return float(self.metadata["threshold_malignant"])

    def check_range(self, values: dict[str, float]) -> None:
        bad = [{"feature": name, "value": values[name], "upper_bound": self._upper[name]}
               for name in FEATURE_ALIASES if values[name] > self._upper[name]]
        if bad:
            raise OutOfRange(bad)

    def build_matrix(self, rows: list[dict[str, float]]) -> np.ndarray:
        """Rows in the training feature order; every row is range-checked first."""
        for row in rows:
            self.check_range(row)
        return np.array([[row[name] for name in FEATURE_ALIASES] for row in rows], dtype=float)

    def predict(self, rows: list[dict[str, float]]) -> list[dict]:
        X = self.build_matrix(rows)
        proba = self.model.predict_proba(X)[:, self._proba_col]
        mapping = self.metadata["class_mapping"]
        results = []
        for p in proba:
            cls = MALIGNANT if p >= self.threshold else 1
            label = mapping[str(cls)]
            results.append({
                "predicted_class": cls,
                "predicted_label": label,
                "predicted_label_vi": LABEL_VI[label],
                "probability_malignant": round(float(p), 4),
                "probability_benign": round(float(1 - p), 4),
                "threshold_malignant": round(self.threshold, 4),
                "model_version": self.metadata["model_version"],
                "warning": self.metadata["warning"],
            })
        return results

    def pick_samples(self, n: int, label: str | None, seed: int | None) -> list[dict]:
        pool = [s for s in self.samples if label is None or s["label"] == label]
        rng = random.Random(seed)
        return rng.sample(pool, min(n, len(pool)))


service = ModelService()
