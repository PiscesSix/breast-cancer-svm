"""Breast cancer SVM API — educational demonstration only.

Run locally:  uvicorn app.main:app --reload
Swagger UI:   http://127.0.0.1:8000/docs      Demo UI: http://127.0.0.1:8000/ui
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.model_service import OutOfRange, service
from app.schemas import (
    FEATURE_ALIASES,
    BatchRequest,
    BatchResponse,
    BreastCancerFeatures,
    PredictionResponse,
    SamplesResponse,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
WARNING = (
    "Chỉ phục vụ mục đích giáo dục, không thay thế chẩn đoán y khoa. "
    "Educational use only; not a medical diagnosis."
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("breast_cancer_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the artifact once at startup; a failure is reported by /health (503), not a crash loop."""
    service.load()
    if service.ready:
        log.info("model loaded version=%s threshold=%s", service.metadata["model_version"], service.threshold)
    else:
        log.error("model not loaded: %s", service.error)
    yield


app = FastAPI(
    title="Breast Cancer SVM API",
    version="1.0.0",
    description=(
        "Chẩn đoán minh hoạ khối u vú lành tính / ác tính từ 30 đặc trưng tế bào (Breast Cancer Wisconsin "
        "Diagnostic) bằng SVM. **Chỉ phục vụ mục đích giáo dục, không thay thế chẩn đoán y khoa.** "
        "Không gửi tên, mã bệnh nhân hay bất kỳ dữ liệu định danh nào."
    ),
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def request_log(request: Request, call_next):
    """Log request id, path, status and latency only — never the medical payload."""
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    log.info("request_id=%s method=%s path=%s status=%s latency_ms=%.1f",
             request_id, request.method, request.url.path, response.status_code, elapsed_ms)
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    """422 with FastAPI's usual detail plus the lecture's missing / extra lists of feature names."""
    missing, extra = set(), set()
    for err in exc.errors():
        name = str(err["loc"][-1]) if err.get("loc") else ""
        if err["type"] == "missing" and name in FEATURE_ALIASES:
            missing.add(name)
        elif err["type"] == "extra_forbidden":
            extra.add(name)
    body = {"detail": jsonable_errors(exc.errors())}
    if missing or extra:
        body["missing"] = sorted(missing, key=FEATURE_ALIASES.index)
        body["extra"] = sorted(extra)
    return JSONResponse(status_code=422, content=body)


def jsonable_errors(errors) -> list[dict]:
    # "input" may hold NaN or the whole payload: drop it so nothing medical is echoed or logged.
    return [{k: v for k, v in err.items() if k in ("type", "loc", "msg")} for err in errors]


def require_model():
    if not service.ready:
        raise HTTPException(status_code=503, detail=service.error or "Mô hình chưa sẵn sàng")


def run_prediction(rows: list[dict[str, float]]) -> list[dict]:
    require_model()
    try:
        return service.predict(rows)
    except OutOfRange as exc:
        raise HTTPException(status_code=422, detail={
            "message": "Giá trị vượt quá 3 lần mức lớn nhất quan sát được trong dữ liệu huấn luyện",
            "out_of_range": exc.fields,
        }) from exc


@app.get("/", tags=["Dịch vụ"], response_model=None)
def root(request: Request):
    """Service info as JSON; a browser (Accept: text/html) gets the demo UI instead."""
    if "text/html" in request.headers.get("accept", ""):
        return FileResponse(STATIC_DIR / "index.html")
    return {
        "service": "Breast Cancer SVM API",
        "docs": "/docs",
        "ui": "/ui",
        "model_version": service.metadata.get("model_version"),
        "warning": WARNING,
    }


@app.get("/ui", include_in_schema=False)
def ui():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", tags=["Dịch vụ"])
def health():
    """200 when the artifact is loaded, 503 otherwise (Render's health check)."""
    if not service.ready:
        return JSONResponse(status_code=503, content={
            "status": "unavailable", "model_loaded": False, "error": service.error})
    return {"status": "ok", "model_loaded": True, "model_version": service.metadata["model_version"],
            "threshold_malignant": service.threshold}


@app.get("/metadata", tags=["Dịch vụ"])
def metadata():
    """Version, feature names and bounds, class mapping, threshold, training summary and warning."""
    require_model()
    return service.metadata


@app.post("/predict", response_model=PredictionResponse, tags=["Dự đoán"])
def predict(payload: BreastCancerFeatures, request: Request):
    """Predict one record. Body: the 30 features, flat or wrapped as {"features": {...}}."""
    result = run_prediction([payload.by_dataset_name()])[0]
    log.info("request_id=%s prediction=%s", request.state.request_id, result["predicted_label"])
    return result


@app.post("/predict/batch", response_model=BatchResponse, tags=["Dự đoán"])
def predict_batch(payload: BatchRequest, request: Request):
    """Predict up to 100 records at once: {"items": [record, ...]}."""
    results = run_prediction([item.by_dataset_name() for item in payload.items])
    n_malignant = sum(r["predicted_class"] == 0 for r in results)
    log.info("request_id=%s batch=%d malignant=%d", request.state.request_id, len(results), n_malignant)
    return {"count": len(results), "n_malignant": n_malignant, "results": results,
            "model_version": service.metadata["model_version"], "warning": service.metadata["warning"]}


@app.get("/samples", response_model=SamplesResponse, tags=["Dữ liệu mẫu"])
def samples(
    n: int = Query(5, ge=1, le=50, description="Số mẫu"),
    label: Literal["malignant", "benign"] | None = Query(None, description="Lọc theo nhãn thật"),
    seed: int | None = Query(None, description="Cố định để lấy lại đúng các mẫu cũ"),
):
    """Random records from the held-out test split, with their true label (so the demo needs no typing)."""
    require_model()
    items = service.pick_samples(n, label, seed)
    return {"source": "tập kiểm tra (test split 20%, random_state=42)", "count": len(items), "items": items}
