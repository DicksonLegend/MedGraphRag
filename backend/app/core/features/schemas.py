"""
MedGraphRAG Backend — Feature Layer Schemas (Step 13)
=====================================================
Pydantic data models for:
  1. MedTrend: Longitudinal lab trajectory tracking across user's private reports.
  2. CareGap: Report <-> guideline reconciliation (out-of-target & missing checks).
  3. Evidence Coverage Map: Query sub-question decomposition, hybrid retrieval scoring,
     and coverage classification with rephrase generation.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Feature 1: MedTrend Schemas
# ---------------------------------------------------------------------------

class TrendDirection(str, Enum):
    WORSENING = "worsening"
    IMPROVING = "improving"
    STABLE = "stable"
    NEW = "new"
    RESOLVED = "resolved"


class LabMeasurement(BaseModel):
    """A single lab measurement point in time."""
    report_id: str = Field(..., description="Unique report identifier")
    report_date: str = Field(..., description="Report date YYYY-MM-DD or upload timestamp")
    value: float = Field(..., description="Standardized numeric value")
    unit: str = Field(..., description="Standardized unit")
    ref_low: Optional[float] = Field(None, description="Normal reference range lower bound")
    ref_high: Optional[float] = Field(None, description="Normal reference range upper bound")
    is_critical: bool = Field(False, description="Flag indicating if measurement is critical")


class GraphCausePath(BaseModel):
    """Graph path connecting a lab test to a possible related condition."""
    test_name: str = Field(..., description="Canonical lab test name")
    disease_name: str = Field(..., description="Associated condition or disease")
    edge_type: str = Field("LABTEST_RELATED_TO", description="Graph relationship type")
    graph_path_str: str = Field(..., description="Formatted string representation of graph path")


class TrendItem(BaseModel):
    """Longitudinal trajectory for a specific lab test."""
    test_name: str = Field(..., description="Canonical lab test name")
    canonical_unit: str = Field(..., description="Standardized unit for comparison")
    measurements: List[LabMeasurement] = Field(default_factory=list, description="Chronological measurements")
    measurement_count: int = Field(..., description="Total measurements recorded")
    earliest_date: Optional[str] = Field(None, description="Earliest measurement date")
    latest_date: Optional[str] = Field(None, description="Latest measurement date")
    earliest_value: Optional[float] = Field(None, description="Earliest recorded value")
    latest_value: Optional[float] = Field(None, description="Latest recorded value")
    delta: Optional[float] = Field(None, description="Latest value minus earliest value")
    rate_per_month: Optional[float] = Field(None, description="Change per month over time span")
    direction: TrendDirection = Field(..., description="worsening | improving | stable | new | resolved")
    is_significant: bool = Field(False, description="True if value crosses reference boundary or large delta")
    significance_reason: Optional[str] = Field(None, description="Explanation for why trend is significant")
    possible_causes: List[GraphCausePath] = Field(default_factory=list, description="Graph-derived related conditions")
    clinical_framing: str = Field(
        "Discuss this trajectory with your physician.",
        description="Clinical contextual framing",
    )


class TrendResult(BaseModel):
    """Final output for MedTrend analysis."""
    user_id: str = Field(..., description="User ID associated with private store")
    trends: List[TrendItem] = Field(default_factory=list, description="Analyzed lab trends")
    significant_count: int = Field(0, description="Number of significant trends flagged")
    summary_text: str = Field(..., description="Plain-language non-diagnostic summary")
    provenance: List[str] = Field(default_factory=list, description="List of graph path / report references")
    disclaimer: str = Field(
        "This is information, not medical advice — consult your physician.",
        description="Mandatory medical disclaimer",
    )
    disclaimer_present: bool = True


# ---------------------------------------------------------------------------
# Feature 2: CareGap Schemas
# ---------------------------------------------------------------------------

class GapType(str, Enum):
    OUT_OF_TARGET = "out_of_target"
    MISSING_RECOMMENDED_CHECK = "missing_recommended_check"


class GapItem(BaseModel):
    """An identified care gap or clinical discrepancy."""
    gap_type: GapType = Field(..., description="out_of_target | missing_recommended_check")
    condition_or_topic: str = Field(..., description="Relevant condition (e.g. Type 2 Diabetes, Hypertension)")
    recommended_check: str = Field(..., description="Lab test or monitoring metric")
    observed_value: Optional[str] = Field(None, description="Observed value from report if present")
    guideline_target: str = Field(..., description="Guideline target threshold or recommended interval")
    status: str = Field(..., description="Status description")
    guideline_provenance: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Guideline citations including document_id, source, and snippet",
    )
    recommendation_text: str = Field(
        "Discuss with your doctor regarding recommended monitoring.",
        description="Clinical discussion framing",
    )


class CareGapResult(BaseModel):
    """Final output for CareGap analysis."""
    user_id: str = Field(..., description="User ID associated with private store")
    report_id: Optional[str] = Field(None, description="Evaluated report ID")
    gaps: List[GapItem] = Field(default_factory=list, description="List of identified care gaps")
    total_gaps: int = Field(0, description="Total number of gaps identified")
    out_of_target_count: int = Field(0, description="Count of out-of-target values")
    missing_check_count: int = Field(0, description="Count of missing recommended checks")
    summary_text: str = Field(..., description="Plain-language non-diagnostic summary")
    provenance: List[str] = Field(default_factory=list, description="All cited guideline document IDs")
    disclaimer: str = Field(
        "This is information, not medical advice — consult your physician.",
        description="Mandatory medical disclaimer",
    )
    disclaimer_present: bool = True


# ---------------------------------------------------------------------------
# Feature 3: Evidence Coverage Map Schemas
# ---------------------------------------------------------------------------

class CoverageClass(str, Enum):
    STRONG = "strong"
    PARTIAL = "partial"
    NONE = "none"


class SubQuestionCoverage(BaseModel):
    """Coverage evaluation for an atomic sub-question."""
    sub_question: str = Field(..., description="Decomposed sub-question query")
    coverage_class: CoverageClass = Field(..., description="strong | partial | none")
    top_fused_score: float = Field(..., description="Top RRF fused score from retrieval")
    distinct_doc_count: int = Field(..., description="Number of distinct source documents")
    evidence_count: int = Field(..., description="Total retrieved evidence items")
    top_citations: List[str] = Field(default_factory=list, description="Sample citation snippets/document IDs")
    suggested_rephrase: Optional[str] = Field(
        None,
        description="Suggested query refinement if coverage is low or none",
    )


class CoverageMap(BaseModel):
    """Evidence Coverage Map decomposed across sub-questions."""
    query: str = Field(..., description="Original user query")
    sub_questions: List[SubQuestionCoverage] = Field(default_factory=list, description="Evaluated sub-questions")
    overall_coverage: CoverageClass = Field(..., description="Overall query coverage tier")
    strong_count: int = Field(0, description="Number of strongly covered sub-questions")
    partial_count: int = Field(0, description="Number of partially covered sub-questions")
    none_count: int = Field(0, description="Number of uncovered sub-questions")
    suggested_rephrases: List[str] = Field(default_factory=list, description="All suggested rephrases")
    disclaimer: str = Field(
        "This is information, not medical advice — consult your physician.",
        description="Mandatory medical disclaimer",
    )
    disclaimer_present: bool = True
