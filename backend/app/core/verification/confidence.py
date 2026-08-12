"""
MedGraphRAG Backend — Confidence Calculator
=============================================
Combines evidence_confidence (retrieval quality) and faithfulness_score (LLM factual adherence)
into a single final_confidence score and assigns confidence_tier ('high' | 'medium' | 'low').
"""

from __future__ import annotations

import logging
from typing import Tuple

from app.config import settings

logger = logging.getLogger(__name__)


def compute_final_confidence(
    evidence_confidence: float,
    faithfulness_score: float,
) -> Tuple[float, str]:
    """
    Compute final_confidence and determine confidence_tier.

    Formula:
      final_confidence = (w_e * evidence_confidence) + (w_f * faithfulness_score)

    Tiers:
      HIGH   : final_confidence >= 0.75
      MEDIUM : 0.50 <= final_confidence < 0.75
      LOW    : final_confidence < 0.50

    Parameters
    ----------
    evidence_confidence : float
        Retrieval quality score from Step 7 (0.0 - 1.0).
    faithfulness_score : float
        LLM claim faithfulness score from Stage B (0.0 - 1.0).

    Returns
    -------
    tuple of (final_confidence: float, confidence_tier: str)
    """
    w_e = settings.verification_w_evidence
    w_f = settings.verification_w_faithfulness

    final_score = round(w_e * evidence_confidence + w_f * faithfulness_score, 3)
    final_score = min(1.0, max(0.0, final_score))

    if final_score >= settings.verification_threshold_high:
        tier = "high"
    elif final_score >= settings.verification_threshold_medium:
        tier = "medium"
    else:
        tier = "low"

    logger.debug(
        "Computed final_confidence: %.3f (tier=%s, evidence_conf=%.3f, faithfulness=%.3f)",
        final_score, tier, evidence_confidence, faithfulness_score
    )
    return final_score, tier
