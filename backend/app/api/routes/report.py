"""
MedGraphRAG Backend — Multipart Diagnostic Report Route Handler
=================================================================
POST /report
Accepts diagnostic report files (PDF, PNG, JPG, XLSX, CSV).
Amendment 3: PIN /report routing via AgentOrchestrator().answer(route="report", ...).
Enforces 20 MB max upload limit (413) and allowed extensions (415).
Enforces single-flight LLM serialization lock and non-blocking asyncio.to_thread execution.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

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
            # Amendment 3: PIN /report routing via AgentOrchestrator().answer()
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
