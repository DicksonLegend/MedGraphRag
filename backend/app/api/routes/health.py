"""
MedGraphRAG Backend — Health Route
===================================
GET /health
Returns system health status and component readiness.
MUST NOT trigger LLM loading — VRAM remains 0 MB until first query/report.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter

import app.core.llm.llm_loader as llm_loader

logger = logging.getLogger(__name__)

router = APIRouter(tags=["System Health"])


@router.get("/health")

@router.get("/api/v1/health")
async def health_check() -> Dict[str, Any]:
    """
    System readiness and health status check.
    Does NOT load the LLM model weights; checks singleton state safely.
    """
    is_llm_loaded = llm_loader._llm_instance is not None

    return {
        "status": "ok",
        "components": {
            "retrieval": "ok",
            "graph": "ok",
            "llm_loaded": is_llm_loaded,
        },
        "version": "1.0.0",
    }
