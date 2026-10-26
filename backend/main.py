"""FastAPI application for the RegulaTrace Presentation Edition."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.engine import ENGINE_VERSION, analyze_document, compare_policy, compare_versions
from backend.evaluation import run_benchmark
from backend.ingestion import IngestionError, extract_document
from backend.storage import audit_trail, dashboard, get_analysis, list_analyses, record_review, save_analysis
from backend.schemas import (
    AnalysisHistoryItem,
    AnalyzeRequest,
    AnalysisResponse,
    AuditEvent,
    BenchmarkResponse,
    CompareRequest,
    ComparisonResponse,
    DashboardResponse,
    ErrorResponse,
    HealthResponse,
    IngestResponse,
    ReviewRequest,
    ReviewResponse,
    VersionCompareRequest,
    VersionCompareResponse,
)


def _cors_origins() -> list[str]:
    configured = os.getenv("REGULATRACE_CORS_ORIGINS")
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return [
        "http://127.0.0.1:4173", "http://localhost:4173",
        "http://127.0.0.1:4174", "http://localhost:4174",
    ]


app = FastAPI(
    title="RegulaTrace Compliance Intelligence API",
    description=(
        "Presentation-ready evidence-linked regulatory obligation extraction, "
        "document ingestion, policy comparison, version change analysis, persistent "
        "human review, audit trails, and executable evaluation."
    ),
    version="2.0.0-presentation",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder({"error": {"code": "VALIDATION_ERROR", "message": "The request payload is invalid.", "details": exc.errors()}}),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": detail.get("code", "REQUEST_ERROR"), "message": detail.get("message", "Request failed."), "details": detail.get("details")}},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "RegulaTrace could not complete the deterministic analysis.", "details": None}},
    )


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    422: {"model": ErrorResponse, "description": "Invalid input"},
    500: {"model": ErrorResponse, "description": "Unexpected analysis failure"},
}


@app.get("/api/health", response_model=HealthResponse, tags=["System"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "regulatrace-api", "phase": "presentation-edition", "engineVersion": ENGINE_VERSION}


@app.post("/api/analyze", response_model=AnalysisResponse, responses=ERROR_RESPONSES, tags=["Analysis"])
def analyze(request: AnalyzeRequest) -> dict[str, Any]:
    metadata = request.source_metadata.model_dump(by_alias=True, exclude_none=True)
    result = analyze_document(request.text, metadata)
    if request.persist:
        save_analysis(result)
    return result


@app.post("/api/compare", response_model=ComparisonResponse, responses=ERROR_RESPONSES, tags=["Analysis"])
def compare(request: CompareRequest) -> dict[str, Any]:
    return compare_policy(request.regulatory_text, request.policy_text)


@app.post("/api/versions/compare", response_model=VersionCompareResponse, responses=ERROR_RESPONSES, tags=["Analysis"])
def versions_compare(request: VersionCompareRequest) -> dict[str, Any]:
    return compare_versions(request.old_text, request.new_text)


@app.post("/api/documents/ingest", response_model=IngestResponse, responses=ERROR_RESPONSES, tags=["Documents"])
async def ingest_document(file: UploadFile = File(...)) -> dict[str, object]:
    try:
        content = await file.read()
        return extract_document(file.filename or "document.txt", content)
    except IngestionError as exc:
        raise HTTPException(status_code=422, detail={"code": "INGESTION_ERROR", "message": str(exc)}) from exc
    finally:
        await file.close()


@app.get("/api/analyses", response_model=list[AnalysisHistoryItem], tags=["Cases"])
def analyses_history(limit: int = 12) -> list[dict[str, Any]]:
    return list_analyses(max(1, min(limit, 100)))


@app.get("/api/analyses/{analysis_id}", response_model=AnalysisResponse, responses=ERROR_RESPONSES, tags=["Cases"])
def analysis_detail(analysis_id: str) -> dict[str, Any]:
    result = get_analysis(analysis_id)
    if result is None:
        raise HTTPException(status_code=404, detail={"code": "ANALYSIS_NOT_FOUND", "message": "The requested analysis does not exist."})
    return result


@app.post("/api/reviews", response_model=ReviewResponse, responses=ERROR_RESPONSES, tags=["Cases"])
def review(request: ReviewRequest) -> dict[str, Any]:
    try:
        event = record_review(
            request.analysis_id,
            request.record_id,
            request.decision,
            request.note,
            request.reviewer,
            request.corrected_fields,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_CORRECTION", "message": str(exc)}) from exc
    if event is None:
        raise HTTPException(status_code=404, detail={"code": "RECORD_NOT_FOUND", "message": "The analysis or obligation record does not exist."})
    return event


@app.get("/api/analyses/{analysis_id}/audit", response_model=list[AuditEvent], tags=["Cases"])
def analysis_audit(analysis_id: str) -> list[dict[str, Any]]:
    if get_analysis(analysis_id) is None:
        raise HTTPException(status_code=404, detail={"code": "ANALYSIS_NOT_FOUND", "message": "The requested analysis does not exist."})
    return audit_trail(analysis_id)


@app.get("/api/dashboard", response_model=DashboardResponse, tags=["System"])
def dashboard_summary() -> dict[str, Any]:
    return dashboard()


@app.get("/api/evaluate", response_model=BenchmarkResponse, tags=["Evaluation"])
def evaluate() -> dict[str, Any]:
    return run_benchmark()


DIST_DIRECTORY = Path(__file__).resolve().parents[1] / "dist"
if DIST_DIRECTORY.exists():
    app.mount("/", StaticFiles(directory=DIST_DIRECTORY, html=True), name="frontend")

