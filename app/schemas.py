"""Request and response models of the API.

The 30 features are declared one by one (Python name + the exact dataset name as alias), so
Swagger shows a precise schema and a typo is rejected instead of silently ignored. Values must be
real JSON numbers: strings, null, booleans, NaN and infinity are all rejected with 422.

Lower bounds: 24 measurements are strictly positive in the dataset; the six concavity /
concave-points features are exactly 0 in 13 real samples, so those six accept 0. Upper bounds
(3x the training maximum) depend on the trained artifact and are checked in model_service.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

Positive = Annotated[float, Field(strict=True, allow_inf_nan=False, gt=0)]
NonNegative = Annotated[float, Field(strict=True, allow_inf_nan=False, ge=0)]

# Sample test-000 of the saved test split (true label: malignant), used as the Swagger example.
EXAMPLE = {
    "mean radius": 19.55, "mean texture": 28.77, "mean perimeter": 133.6, "mean area": 1207.0,
    "mean smoothness": 0.0926, "mean compactness": 0.2063, "mean concavity": 0.1784, "mean concave points": 0.1144,
    "mean symmetry": 0.1893, "mean fractal dimension": 0.06232, "radius error": 0.8426, "texture error": 1.199,
    "perimeter error": 7.158, "area error": 106.4, "smoothness error": 0.006356, "compactness error": 0.04765,
    "concavity error": 0.03863, "concave points error": 0.01519, "symmetry error": 0.01936,
    "fractal dimension error": 0.005252,
    "worst radius": 25.05, "worst texture": 36.27, "worst perimeter": 178.6, "worst area": 1926.0,
    "worst smoothness": 0.1281, "worst compactness": 0.5329, "worst concavity": 0.4251, "worst concave points": 0.1941,
    "worst symmetry": 0.2818, "worst fractal dimension": 0.1005,
}


class BreastCancerFeatures(BaseModel):
    """The 30 measurements of one fine-needle aspirate image (same names as load_breast_cancer)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, json_schema_extra={"example": EXAMPLE})

    mean_radius: Positive = Field(alias="mean radius")
    mean_texture: Positive = Field(alias="mean texture")
    mean_perimeter: Positive = Field(alias="mean perimeter")
    mean_area: Positive = Field(alias="mean area")
    mean_smoothness: Positive = Field(alias="mean smoothness")
    mean_compactness: Positive = Field(alias="mean compactness")
    mean_concavity: NonNegative = Field(alias="mean concavity")
    mean_concave_points: NonNegative = Field(alias="mean concave points")
    mean_symmetry: Positive = Field(alias="mean symmetry")
    mean_fractal_dimension: Positive = Field(alias="mean fractal dimension")

    radius_error: Positive = Field(alias="radius error")
    texture_error: Positive = Field(alias="texture error")
    perimeter_error: Positive = Field(alias="perimeter error")
    area_error: Positive = Field(alias="area error")
    smoothness_error: Positive = Field(alias="smoothness error")
    compactness_error: Positive = Field(alias="compactness error")
    concavity_error: NonNegative = Field(alias="concavity error")
    concave_points_error: NonNegative = Field(alias="concave points error")
    symmetry_error: Positive = Field(alias="symmetry error")
    fractal_dimension_error: Positive = Field(alias="fractal dimension error")

    worst_radius: Positive = Field(alias="worst radius")
    worst_texture: Positive = Field(alias="worst texture")
    worst_perimeter: Positive = Field(alias="worst perimeter")
    worst_area: Positive = Field(alias="worst area")
    worst_smoothness: Positive = Field(alias="worst smoothness")
    worst_compactness: Positive = Field(alias="worst compactness")
    worst_concavity: NonNegative = Field(alias="worst concavity")
    worst_concave_points: NonNegative = Field(alias="worst concave points")
    worst_symmetry: Positive = Field(alias="worst symmetry")
    worst_fractal_dimension: Positive = Field(alias="worst fractal dimension")

    @model_validator(mode="before")
    @classmethod
    def unwrap_features(cls, data: Any) -> Any:
        """Also accept the lecture's shape {"features": {...}}."""
        if isinstance(data, dict) and set(data) == {"features"} and isinstance(data["features"], dict):
            return data["features"]
        return data

    def by_dataset_name(self) -> dict[str, float]:
        return self.model_dump(by_alias=True)


FEATURE_ALIASES = [field.alias for field in BreastCancerFeatures.model_fields.values()]


class BatchRequest(BaseModel):
    """Up to 100 records, each in either accepted shape."""

    model_config = ConfigDict(extra="forbid")

    items: list[BreastCancerFeatures] = Field(..., min_length=1, max_length=100)


class PredictionResponse(BaseModel):
    predicted_class: int = Field(description="0 = malignant, 1 = benign (theo target_names của dataset)")
    predicted_label: str = Field(description="malignant hoặc benign")
    predicted_label_vi: str = Field(description="Ác tính hoặc Lành tính")
    probability_malignant: float
    probability_benign: float
    threshold_malignant: float = Field(description="Dự đoán ác tính khi probability_malignant >= ngưỡng này")
    inference_ms: float = Field(description="Thời gian predict_proba phía server cho mỗi mẫu (ms)")
    model_version: str
    warning: str


class BatchResponse(BaseModel):
    count: int
    n_malignant: int
    results: list[PredictionResponse]
    model_version: str
    warning: str


class Sample(BaseModel):
    id: str
    label: str
    features: dict[str, float]


class SamplesResponse(BaseModel):
    source: str
    count: int
    items: list[Sample]
