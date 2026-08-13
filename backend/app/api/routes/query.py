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

    logger.info("Received /query from user %s (dest=%s, query=%r)", user_id, dest, req.query[:60])

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
            )
            return response
    except Exception as e:
        logger.error("Query execution failed for user %s: %s", user_id, e, exc_info=True)
        return {
            "route": "medical_query",
            "answer_text": (
                f"An error occurred while processing your query.\n\n"
                "This is information, not medical advice — consult your physician."
            ),
            "answer_status": "error",
            "confidence_tier": "low",
            "final_confidence": 0.0,
            "citations": [],
            "graph_paths": [],
            "disclaimer_present": True,
            "error": "query_processing_error",
            "detail": "Failed to process query cleanly.",
        }
