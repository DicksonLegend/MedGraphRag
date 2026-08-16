"""
MedGraphRAG Backend — Multipart Diagnostic Report Route Handler
=================================================================
POST /report
Accepts diagnostic report files (PDF, PNG, JPG, XLSX, CSV).
GET /reports
Returns list of summary report records for the authenticated user.
GET /reports/{report_id}
Returns detailed report record with full lab values for the authenticated user.
Enforces 20 MB max upload limit (413) and allowed extensions (415).
Enforces single-flight LLM serialization lock and non-blocking asyncio.to_thread execution.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_llm_lock
from app.config import settings
from app.core.agents.service import AgentOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Report Interpretation"])

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".xlsx", ".csv"}


@router.post("/report")
@router.post("/api/v1/report")
async def process_report(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
    llm_lock: asyncio.Lock = Depends(get_llm_lock),
) -> Dict[str, Any]:
    """
    Upload and interpret diagnostic lab report file.
    """
    user_id = current_user["user_id"]
    filename = file.filename or "report.txt"
    ext = Path(filename).suffix.lower()

    # 1. Extension Validation (415 Unsupported Media Type)
    if ext not in ALLOWED_EXTENSIONS:
        logger.warning("Rejected upload for user %s: Unsupported format %s", user_id, ext)
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file format '{ext}'. Allowed formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # 2. File Size Read & Validation (413 Payload Too Large)
    content = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        logger.warning("Rejected upload for user %s: File size %d bytes > max %d MB", user_id, len(content), settings.max_upload_mb)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed limit of {settings.max_upload_mb} MB.",
        )

    logger.info("Received /report upload from user %s (filename=%s, size=%d bytes)", user_id, filename, len(content))

    report_payload = {
        "file_bytes": content,
        "filename": filename,
    }

    try:
        # Single-flight serialization lock
        async with llm_lock:
            orchestrator = AgentOrchestrator()
            response = await asyncio.to_thread(
                orchestrator.answer,
                query="Diagnostic Report Analysis",
                user_id=user_id,
                destination=f"private_store/{user_id}",
                report_payload=report_payload,
            )

            # Privacy logging: log metadata only, NEVER raw lab values or report text
            status_str = response.get("answer_status", "unknown")
            route_str = response.get("route", "report")
            lat_ms = response.get("latency_breakdown", {}).get("total", 0.0)
            logger.info("Report execution complete for user %s (route=%s, status=%s, total_ms=%.2f)", user_id, route_str, status_str, lat_ms)

            return response
    except Exception as e:
        logger.error("Report execution failed for user %s: %s", user_id, e, exc_info=True)
        return {
            "route": "report",
            "answer_text": (
                "An error occurred while processing your diagnostic report.\n\n"
                "This is information, not medical advice — consult your physician."
            ),
            "answer_status": "error",
            "confidence_tier": "low",
            "final_confidence": 0.0,
            "citations": [],
            "graph_paths": [],
            "disclaimer_present": True,
            "error": "report_processing_error",
            "detail": "Failed to interpret diagnostic report cleanly.",
        }


class ReportSummaryItem(BaseModel):
    report_id: str
    report_date: str
    filename: str
    n_lab_values: int
    critical_flag: bool


class LabValueDetailItem(BaseModel):
    test_name: str
    value: float
    unit: str
    ref_low: Optional[float] = None
    ref_high: Optional[float] = None
    is_critical: bool = False


class ReportDetailResponse(BaseModel):
    report_id: str
    report_date: str
    filename: str
    lab_values: List[LabValueDetailItem] = Field(default_factory=list)


@router.get("/reports", response_model=List[ReportSummaryItem])
@router.get("/api/v1/reports", response_model=List[ReportSummaryItem])
async def list_user_reports(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> List[ReportSummaryItem]:
    """
    Return the authenticated user's report list from their private store metadata.
    Includes guest users. Scoped strictly to the authenticated user's private store.
    """
    user_id = current_user["user_id"]
    user_dir = settings.private_store_dir / user_id

    if not user_dir.exists():
        return []

    reports: List[ReportSummaryItem] = []
    seen_ids = set()

    # 1. Query private Kùzu DB if present
    db_path = user_dir / "kuzu" / "private_kuzu_db"
    if db_path.exists():
        try:
            import kuzu
            db = kuzu.Database(str(db_path), read_only=True)
            conn = kuzu.Connection(db)
            try:
                # Implicit grouping via aggregation in Kùzu Cypher
                query = """
                MATCH (r:Report)-[:HAS_LAB_VALUE]->(lv:LabValue)
                RETURN r.id AS report_id, r.report_date AS report_date, r.filename AS filename,
                       count(lv) AS n_lab_values,
                       sum(CASE WHEN lv.is_critical THEN 1 ELSE 0 END) AS n_critical
                ORDER BY report_date DESC
                """
                df = conn.execute(query).get_as_df()
                for _, row in df.iterrows():
                    rid = str(row["report_id"])
                    if rid not in seen_ids:
                        seen_ids.add(rid)
                        n_crit = int(row.get("n_critical", 0))
                        n_lv = int(row.get("n_lab_values", 0))
                        reports.append(
                            ReportSummaryItem(
                                report_id=rid,
                                report_date=str(row.get("report_date", "")),
                                filename=str(row.get("filename", f"report_{rid}")),
                                n_lab_values=n_lv,
                                critical_flag=(n_crit > 0),
                            )
                        )
            finally:
                del conn
                del db
        except Exception as e:
            logger.debug("Private Kùzu report query fallback for user %s: %s", user_id, e)

    # 2. Fallback to decrypted payload if no Report nodes found
    if not reports:
        from app.core.report.store import load_private_decrypted_payload
        payload = load_private_decrypted_payload(user_id)
        if payload:
            asms = payload.get("assessments", [])
            has_crit = any(a.get("is_critical", False) for a in asms)
            rid = payload.get("report_id", f"rep_{user_id[:8]}")
            reports.append(
                ReportSummaryItem(
                    report_id=rid,
                    report_date=payload.get("report_date", "2026-08-12"),
                    filename=payload.get("filename", "diagnostic_report.pdf"),
                    n_lab_values=len(asms),
                    critical_flag=has_crit,
                )
            )

    return reports


@router.get("/reports/{report_id}", response_model=ReportDetailResponse)
@router.get("/api/v1/reports/{report_id}", response_model=ReportDetailResponse)
async def get_user_report_detail(
    report_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> ReportDetailResponse:
    """
    Return detailed lab measurements for a specific report owned by the authenticated user.
    Strict user isolation: Returns 404 for missing or unauthorized report IDs.
    """
    user_id = current_user["user_id"]
    user_dir = settings.private_store_dir / user_id

    if not user_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report '{report_id}' not found in user private store.",
        )

    db_path = user_dir / "kuzu" / "private_kuzu_db"
    if db_path.exists():
        try:
            import kuzu
            db = kuzu.Database(str(db_path), read_only=True)
            conn = kuzu.Connection(db)
            try:
                query = f"""
                MATCH (r:Report {{id: '{report_id}'}})-[:HAS_LAB_VALUE]->(lv:LabValue)
                RETURN r.id AS report_id, r.report_date AS report_date, r.filename AS filename,
                       lv.test_name AS test_name, lv.value AS value, lv.unit AS unit,
                       lv.ref_low AS ref_low, lv.ref_high AS ref_high, lv.is_critical AS is_critical
                ORDER BY lv.test_name ASC
                """
                df = conn.execute(query).get_as_df()
                if not df.empty:
                    first_row = df.iloc[0]
                    lab_values = []
                    for _, row in df.iterrows():
                        r_low = float(row["ref_low"]) if row["ref_low"] is not None and row["ref_low"] > 0 else None
                        r_high = float(row["ref_high"]) if row["ref_high"] is not None and row["ref_high"] < 9000 else None
                        lab_values.append(
                            LabValueDetailItem(
                                test_name=str(row["test_name"]),
                                value=float(row["value"]),
                                unit=str(row["unit"]),
                                ref_low=r_low,
                                ref_high=r_high,
                                is_critical=bool(row["is_critical"]),
                            )
                        )
                    return ReportDetailResponse(
                        report_id=str(first_row["report_id"]),
                        report_date=str(first_row["report_date"]),
                        filename=str(first_row["filename"]),
                        lab_values=lab_values,
                    )
            finally:
                del conn
                del db
        except Exception as e:
            logger.debug("Error querying Kùzu report detail for %s: %s", report_id, e)

    # Fallback to decrypted payload if report_id matches
    from app.core.report.store import load_private_decrypted_payload
    payload = load_private_decrypted_payload(user_id)
    if payload:
        payload_rid = payload.get("report_id", f"rep_{user_id[:8]}")
        if payload_rid == report_id or report_id == "report_meta":
            asms = payload.get("assessments", [])
            lab_values = []
            for asm in asms:
                nlv = asm.get("normalized_lab_value", {})
                t_name = nlv.get("canonical_test_name") or asm.get("test_name", "Unknown")
                val = float(nlv.get("normalized_value", 0.0))
                unit = nlv.get("normalized_unit", "")
                lab_values.append(
                    LabValueDetailItem(
                        test_name=t_name,
                        value=val,
                        unit=unit,
                        ref_low=None,
                        ref_high=None,
                        is_critical=bool(asm.get("is_critical", False)),
                    )
                )
            return ReportDetailResponse(
                report_id=report_id,
                report_date=payload.get("report_date", "2026-08-12"),
                filename=payload.get("filename", "diagnostic_report.pdf"),
                lab_values=lab_values,
            )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Report '{report_id}' not found in user private store.",
    )
