-- 002: the Breast Cancer Wisconsin (Diagnostic) dataset, browsable on the "Dữ liệu SQL" page.
-- seed.py fills the 569 rows of sklearn.datasets.load_breast_cancer once. id is the sklearn row
-- index (sklearn has no WDBC patient ID; row 0 is ID 842302 in the UCI file). split / sample_id
-- repeat the training split (test_size=0.2, stratify, random_state=42); sample_id = test-NNN of
-- artifacts/test_samples.json. Column names follow the Kaggle/UCI CSV (radius_mean ... _se ... _worst).

CREATE TABLE wdbc (
    id                      INTEGER PRIMARY KEY,
    diagnosis               TEXT    NOT NULL CHECK (diagnosis IN ('malignant', 'benign')),
    split                   TEXT    NOT NULL CHECK (split IN ('train', 'test')),
    sample_id               TEXT,
    radius_mean             REAL    NOT NULL,
    texture_mean            REAL    NOT NULL,
    perimeter_mean          REAL    NOT NULL,
    area_mean               REAL    NOT NULL,
    smoothness_mean         REAL    NOT NULL,
    compactness_mean        REAL    NOT NULL,
    concavity_mean          REAL    NOT NULL,
    concave_points_mean     REAL    NOT NULL,
    symmetry_mean           REAL    NOT NULL,
    fractal_dimension_mean  REAL    NOT NULL,
    radius_se               REAL    NOT NULL,
    texture_se              REAL    NOT NULL,
    perimeter_se            REAL    NOT NULL,
    area_se                 REAL    NOT NULL,
    smoothness_se           REAL    NOT NULL,
    compactness_se          REAL    NOT NULL,
    concavity_se            REAL    NOT NULL,
    concave_points_se       REAL    NOT NULL,
    symmetry_se             REAL    NOT NULL,
    fractal_dimension_se    REAL    NOT NULL,
    radius_worst            REAL    NOT NULL,
    texture_worst           REAL    NOT NULL,
    perimeter_worst         REAL    NOT NULL,
    area_worst              REAL    NOT NULL,
    smoothness_worst        REAL    NOT NULL,
    compactness_worst       REAL    NOT NULL,
    concavity_worst         REAL    NOT NULL,
    concave_points_worst    REAL    NOT NULL,
    symmetry_worst          REAL    NOT NULL,
    fractal_dimension_worst REAL    NOT NULL
);
CREATE INDEX idx_wdbc_diagnosis ON wdbc (diagnosis);
