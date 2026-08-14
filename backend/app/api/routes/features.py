"""
MedGraphRAG Backend — Feature Layer REST API Routes (Step 13)
==============================================================
POST /features/trend    — MedTrend: Longitudinal lab trajectory analysis across reports
POST /features/caregap  — CareGap: Guideline reconciliation & missing check detection
POST /features/coverage — Evidence Coverage Map: Query decomposition & retrieval scoring
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_llm_lock
from app.core.features import (
    CareGapResult,
    CoverageMap,
    FeatureService,
    TrendResult,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/features", tags=["Features"])


class CoverageRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Medical query to evaluate for evidence coverage")


@router.post("/trend", response_model=TrendResult)
async def get_trend_analysis(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> TrendResult:
    """
    Retrieve longitudinal lab trajectory analysis across user's private diagnostic reports.
    """
    user_id = current_user["user_id"]
    logger.info("Executing /features/trend for user: %s", user_id)
    try:
        service = FeatureService()
        result = await asyncio.to_thread(service.get_trend, user_id=user_id)
        return result
    except Exception as e:
        logger.error("Failed /features/trend for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate longitudinal trend analysis.",
        )


@router.post("/caregap", response_model=CareGapResult)
async def get_caregap_analysis(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> CareGapResult:
    """
    Reconcile user's latest lab report against evidence-based clinical guidelines to
    identify out-of-target values and missing recommended clinical checks.
    """
    user_id = current_user["user_id"]
    logger.info("Executing /features/caregap for user: %s", user_id)
    try:
        service = FeatureService()
        result = await asyncio.to_thread(service.get_care_gaps, user_id=user_id)
        return result
    except Exception as e:
        logger.error("Failed /features/caregap for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to evaluate clinical care gaps.",
        )


@router.post("/coverage", response_model=CoverageMap)
async def get_coverage_map(
    request: CoverageRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    llm_lock: asyncio.Lock = Depends(get_llm_lock),
) -> CoverageMap:
    """
    Decompose medical query into atomic sub-questions, evaluate hybrid evidence coverage
    per sub-question, and generate actionable query rephrases for low-coverage topics.
    """
    user_id = current_user["user_id"]
    logger.info("Executing /features/coverage for user %s: '%s'", user_id, request.query)
    try:
        async with llm_lock:
            service = FeatureService()
            result = await asyncio.to_thread(service.get_coverage_map, query=request.query)
            return result
    except Exception as e:
        logger.error("Failed /features/coverage for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate evidence coverage map.",
        )
