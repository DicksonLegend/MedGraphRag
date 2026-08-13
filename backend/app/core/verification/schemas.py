"""
MedGraphRAG Backend — Verification Schemas
============================================
Pydantic data models for the Verification Agent:
  - Claim (extracted atomic statements)
  - ClaimVerification (per-claim verdict and rationale)
  - VerifiedAnswerResult (extended RAG response with confidence, status, & metrics)
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.core.context.context_builder import CitationMeta
from app.core.llm.generator import AnswerResult


class Claim(BaseModel):
    """An atomic factual claim extracted from an answer."""

    claim_text: str = Field(description="The atomic factual statement.")
    cited_labels: List[str] = Field(
        default_factory=list,
        description="List of [E#] tags associated with this claim.",
    )
    claim_type: Literal["factual", "recommendation", "value", "refusal"] = Field(
        default="factual",
        description="Category of the claim.",
    )


class ClaimVerification(BaseModel):
    """Verification result for an individual claim."""

    claim: Claim = Field(description="The claim being verified.")
    verdict: Literal["supported", "contradicted", "not_mentioned", "refusal_valid"] = Field(
        description="Verification verdict."
    )
    explanation: str = Field(description="Reasoning / justification for the verdict.")
    cited_snippets: List[str] = Field(
        default_factory=list,
        description="Text snippets of the evidence checked for this claim.",
    )


class VerifiedAnswerResult(AnswerResult):
    """Extends AnswerResult with verification status, faithfulness, and retry details."""

    answer_status: Literal[
        "verified", "caution", "uncertain", "contradiction_detected", "refusal", "error"
    ] = Field(description="Final gated answer status.")

    final_confidence: float = Field(
        description="Combined final confidence score (0.0 - 1.0)."
    )
    confidence_tier: Literal["high", "medium", "low"] = Field(
        description="Confidence tier based on final_confidence."
    )
    faithfulness_score: float = Field(
        description="Computed faithfulness score (0.0 - 1.0) based on claim verdicts."
    )
    claims: List[ClaimVerification] = Field(
        default_factory=list,
        description="List of per-claim verification results.",
    )
    retry_count: int = Field(
        default=0,
        description="Number of retry attempts executed by the RetryGate.",
    )
    retry_confidence_trajectory: List[float] = Field(
        default_factory=list,
        description="History of final_confidence values after each retry attempt.",
    )
    fallback_used: bool = Field(
        default=False,
        description="True if JSON parse fallback was triggered during verification.",
    )
    disclaimer: str = Field(
        default="This is information, not medical advice — consult your physician.",
        description="Mandatory medical disclaimer text.",
    )
