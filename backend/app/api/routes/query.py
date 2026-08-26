"""
MedGraphRAG Backend — Query Route Handler
==========================================
POST /query
Executes standard/knowledge-graph RAG pipeline via AgentOrchestrator.
Enforces single-flight LLM serialization lock, destination security validation,
and non-blocking asyncio.to_thread execution.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_llm_lock
from app.core.agents.service import AgentOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Query RAG Engine"])


class QueryRequest(BaseModel):
    query: str = Field(..., description="Natural language medical query", example="potassium hyperkalemia ECG changes peaked T waves treatment")
    destination: Optional[str] = Field("global", description="Target destination space ('global' or user's own user_id)")
    attached_scan_id: Optional[str] = Field(None, description="Optional scan image_id attached to query for multimodal context")


@router.post("/query")
@router.post("/api/v1/query")
async def process_query(
    req: QueryRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    llm_lock: asyncio.Lock = Depends(get_llm_lock),
) -> Dict[str, Any]:
    """
    Execute self-verifying MedGraphRAG hybrid retrieval & LLM pipeline.
    """
    user_id = current_user["user_id"]
    dest = (req.destination or "global").strip()

    # Amendment 2: Security Destination Validation
    # destination may ONLY be "global" or the authenticated user's own user_id
    if dest != "global" and dest != user_id and dest != f"private_store/{user_id}":
        logger.warning("Forbidden destination access attempt: User %s tried accessing destination %s", user_id, dest)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden_destination", "detail": "You are not authorized to query another user's private store."},
        )

    logger.info(
        "Received /query from user %s (dest=%s, attached_scan=%s, query=%r)",
        user_id,
        dest,
        req.attached_scan_id,
        req.query[:60],
    )

    try:
        # Single-flight serialization lock to prevent concurrent LLM execution
        async with llm_lock:
            orchestrator = AgentOrchestrator()
            # Non-blocking wrapper for blocking pipeline execution
            response = await asyncio.to_thread(
                orchestrator.answer,
                query=req.query,
                user_id=user_id,
                destination=dest,
                attached_scan_id=req.attached_scan_id,
            )

            # Security Logging
            status_str = response.get("answer_status", "unknown")
            route_str = response.get("route", "medical_query")
            lat_ms = response.get("latency_breakdown", {}).get("total", 0.0)
            logger.info("Query execution complete for user %s (route=%s, status=%s, total_ms=%.2f)", user_id, route_str, status_str, lat_ms)

            return response
    except Exception as e:
        logger.error("Query execution failed for user %s: %s", user_id, e, exc_info=True)
        return {
            "route": "medical_query",
            "answer_text": "An internal error occurred while processing your clinical query. Please try again later.",
            "answer_status": "error",
            "confidence_tier": "low",
            "final_confidence": 0.0,
            "citations": [],
            "graph_paths": [],
            "disclaimer_present": True,
            "retry_count": 0,
            "latency_breakdown": {"total": 0.0},
        }
