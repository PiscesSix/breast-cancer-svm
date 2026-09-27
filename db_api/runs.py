"""Training runs: the evaluation table of the five classifiers, stored once per training."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

import security
from db_api.db import get_conn, utc_now

router = APIRouter(prefix="/model-runs", tags=["Kết quả đánh giá"])

METRIC_COLUMNS = ["sensitivity", "specificity", "precision_malignant", "f1_malignant", "roc_auc", "pr_auc",
                  "brier", "threshold", "false_negatives", "false_positives", "cv_mean", "cv_std",
                  "train_seconds", "predict_ms_per_sample"]


class ModelRow(BaseModel):
    model: str
    label: str | None = None
    sensitivity: float
    specificity: float
    precision_malignant: float
    f1_malignant: float
    roc_auc: float
    pr_auc: float
    brier: float
    threshold: float
    false_negatives: int
    false_positives: int
    cv_mean: float
    cv_std: float
    train_seconds: float
    predict_ms_per_sample: float
    best_params: dict = {}


class TrainingRunIn(BaseModel):
    trained_at: str | None = None
    train_size: int | None = None
    test_size: int | None = None
    target_sensitivity: float | None = None
    best_model: str
    total_seconds: float | None = None
    models: list[ModelRow] = Field(..., min_length=1, max_length=10)


def run_with_models(conn, run_row) -> dict:
    models = conn.execute("SELECT * FROM model_runs WHERE run_id = ? ORDER BY id", (run_row["id"],)).fetchall()
    out = dict(run_row)
    out["models"] = [{**dict(m), "best_params": json.loads(m["best_params_json"] or "{}")} for m in models]
    return out


def store_run(conn, user_id: int | None, body: TrainingRunIn) -> int:
    """Insert one training_runs row and its model_runs rows; returns the run id."""
    cur = conn.execute(
        """INSERT INTO training_runs (user_id, created_at, trained_at, train_size, test_size,
                                      target_sensitivity, best_model, total_seconds)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, utc_now(), body.trained_at, body.train_size, body.test_size, body.target_sensitivity,
         body.best_model, body.total_seconds),
    )
    run_id = cur.lastrowid
    columns = ", ".join(METRIC_COLUMNS)
    marks = ", ".join("?" for _ in METRIC_COLUMNS)
    for m in body.models:
        conn.execute(
            f"""INSERT INTO model_runs (run_id, model, label, {columns}, best_params_json, is_best)
                VALUES (?, ?, ?, {marks}, ?, ?)""",
            (run_id, m.model, m.label, *[getattr(m, c) for c in METRIC_COLUMNS],
             json.dumps(m.best_params, ensure_ascii=False), int(m.model == body.best_model)),
        )
    conn.commit()
    return run_id


@router.post("", status_code=status.HTTP_201_CREATED)
def create_model_run(body: TrainingRunIn, user: dict = Depends(security.current_user), conn=Depends(get_conn)):
    """Store the evaluation table of the five classifiers from one training run."""
    run_id = store_run(conn, user["id"], body)
    run = conn.execute("SELECT * FROM training_runs WHERE id = ?", (run_id,)).fetchone()
    return run_with_models(conn, run)


@router.get("")
def list_model_runs(limit: int = Query(20, ge=1, le=100), conn=Depends(get_conn)):
    """Recent training runs, newest first, each with its model rows."""
    rows = conn.execute(
        """SELECT r.*, u.username FROM training_runs r LEFT JOIN users u ON u.id = r.user_id
           ORDER BY r.id DESC LIMIT ?""", (limit,)).fetchall()
    return {"runs": [run_with_models(conn, r) for r in rows]}
