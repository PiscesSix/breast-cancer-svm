-- 001: users, prediction history and the evaluation table of every training run.
-- Timestamps are UTC, ISO 8601 with a trailing Z. Labels are 'malignant' / 'benign'.

CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    NOT NULL
);

CREATE TABLE predictions (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id               INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at            TEXT    NOT NULL,
    model                 TEXT    NOT NULL,
    input_json            TEXT    NOT NULL,
    predicted_label       TEXT    NOT NULL CHECK (predicted_label IN ('malignant', 'benign')),
    probability_malignant REAL,
    threshold             REAL,
    actual_label          TEXT CHECK (actual_label IN ('malignant', 'benign')),
    sample_id             TEXT,
    runtime_ms            REAL,
    batch_id              TEXT
);
CREATE INDEX idx_predictions_user_time ON predictions (user_id, created_at);

CREATE TABLE training_runs (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id            INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at         TEXT    NOT NULL,
    trained_at         TEXT,
    train_size         INTEGER,
    test_size          INTEGER,
    target_sensitivity REAL,
    best_model         TEXT,
    total_seconds      REAL
);

CREATE TABLE model_runs (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                INTEGER NOT NULL REFERENCES training_runs(id) ON DELETE CASCADE,
    model                 TEXT    NOT NULL,
    label                 TEXT,
    sensitivity           REAL,
    specificity           REAL,
    precision_malignant   REAL,
    f1_malignant          REAL,
    roc_auc               REAL,
    pr_auc                REAL,
    brier                 REAL,
    threshold             REAL,
    false_negatives       INTEGER,
    false_positives       INTEGER,
    cv_mean               REAL,
    cv_std                REAL,
    train_seconds         REAL,
    predict_ms_per_sample REAL,
    best_params_json      TEXT,
    is_best               INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_model_runs_run ON model_runs (run_id);
