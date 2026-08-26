"""
MedGraphRAG Backend — Guardrail & Epistemic Schemas
===================================================
Pydantic data models for:
  - F1: Cross-Modal Discrepancy Alerts (Image vs. Text Conflict Guardrail)
  - F2: Epistemic Knowledge Gaps (Ontology & Faithfulness Gap Mapper)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ── F1: Discrepancy Guardrail Models ──────────────────────────────────────────

class DiscrepancyVisualEvidence(BaseModel):
    """Visual finding evidence extracted from image/BiomedCLIP analysis."""
    label: str = Field(..., description="Visual pathology label (e.g. pneumothorax)")
    score: float = Field(..., description="Confidence probability (0.0 - 1.0)")
    negated: bool = Field(False, description="True if visual model predicts finding is absent")
    neg_score: Optional[float] = Field(None, description="Explicit negation score if available")


class DiscrepancyTextEvidence(BaseModel):
    """Textual finding evidence extracted from clinical report or retrieved snippets."""
    snippet: str = Field(..., description="Exact textual excerpt containing the finding")
    source_id: str = Field(..., description="Document or chunk ID of the text source")
    cue: Optional[str] = Field(None, description="Identified negation or assertion cue")
    category: Optional[str] = Field(None, description="Knowledge category (e.g. radiology, guidelines)")


class DiscrepancyAlert(BaseModel):
    """
    Cross-modal discrepancy alert raised when visual analysis contradicts clinical text.
    Escalated to human clinician without autonomous resolution.
    """
    finding: str = Field(..., description="Name of the conflicting medical entity/finding")
    visual_evidence: DiscrepancyVisualEvidence = Field(..., description="Extracted visual evidence")
    text_evidence: DiscrepancyTextEvidence = Field(..., description="Extracted textual evidence")
    graph_provenance: Optional[str] = Field(None, description="Corroborating graph path from report_graph Kùzu DB if available")
    severity: str = Field("MEDIUM", description="Alert severity: 'HIGH' for life-critical conditions, else 'MEDIUM'")
    recommendation: str = Field(
        default="AI does not resolve this conflict — recommend manual radiologist review.",
        description="Clinical safety recommendation for human adjudication."
    )


# ── F2: Epistemic Knowledge Gap Models ───────────────────────────────────────

class KnowledgeGap(BaseModel):
    """
    Epistemic gap identified when a query encounters refusal, low evidence, or unfaithfulness.
    """
    claim_text: str = Field(..., description="Query or candidate claim encountering knowledge boundary")
    gap_type: str = Field(
        ...,
        description="Classification of the epistemic gap: 'corpus_retrieval', 'graph_coverage', or 'evidence_faithfulness'"
    )
    detail: str = Field(..., description="Clinical/technical description of what knowledge is missing")
    suggested_queries: List[str] = Field(default_factory=list, description="Targeted query reformulations or synonym expansions")
    suggested_sources: List[str] = Field(default_factory=list, description="Recommended clinical guideline sources or categories to consult")
