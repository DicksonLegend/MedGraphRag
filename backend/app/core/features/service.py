"""
MedGraphRAG Backend — Feature Layer Orchestrator (Step 13)
===========================================================
Unified service layer orchestrating:
  1. MedTrend: Longitudinal lab trajectory analysis
  2. CareGap: Clinical guideline reconciliation
  3. CoverageMap: Query decomposition & evidence coverage mapping
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.core.features.caregap import CareGapService
from app.core.features.coverage import CoverageMapService
from app.core.features.schemas import (
    CareGapResult,
    CoverageMap,
    TrendResult,
)
from app.core.features.trend import MedTrendService

logger = logging.getLogger(__name__)


class FeatureService:
    """Unified service orchestrator for MedGraphRAG advanced feature capabilities."""

    def __init__(self):
        self.trend_service = MedTrendService()
        self.caregap_service = CareGapService()
        self.coverage_service = CoverageMapService()

    def get_trend(self, user_id: str) -> TrendResult:
        """Execute longitudinal lab trajectory analysis."""
        return self.trend_service.analyze_trends(user_id=user_id)

    def get_care_gaps(self, user_id: str) -> CareGapResult:
        """Execute report-to-guideline care gap reconciliation."""
        return self.caregap_service.evaluate_care_gaps(user_id=user_id)

    def get_coverage_map(self, query: str) -> CoverageMap:
        """Execute query decomposition and evidence coverage assessment."""
        return self.coverage_service.evaluate_coverage(query=query)
