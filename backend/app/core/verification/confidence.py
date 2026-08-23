"""
MedGraphRAG Backend — Confidence Calculator (Step J2)
======================================================
Combines evidence_confidence, faithfulness_score (phi), and graph_consistency_score (S_g)
into a single final_confidence score and assigns confidence_tier ('high' | 'medium' | 'low').

Formulas:
  Combined verification score V:
    - mode == "evidence": V = phi
    - mode == "graph"   : V = S_g
    - mode == "combined": V = beta * phi + (1 - beta) * S_g  (beta = 0.7)
  Final confidence:
    final_confidence = (w_e * evidence_confidence) + (w_f * V)
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

from app.config import settings

logger = logging.getLogger(__name__)


def compute_combined_verification_score(
    faithfulness_score: float,
    graph_consistency_score: Optional[float] = None,
    verify_mode: Optional[str] = None,
    beta: Optional[float] = None,
) -> float:
    """
    Compute combined verification score V.
    """
    phi = max(0.0, min(1.0, float(faithfulness_score)))
    s_g = max(0.0, min(1.0, float(graph_consistency_score if graph_consistency_score is not None else 1.0)))

    mode = (verify_mode or getattr(settings, "verification_mode", "combined")).lower()
    b = beta if beta is not None else getattr(settings, "verification_beta_evidence", 0.7)

    if mode == "evidence":
        v = phi
    elif mode == "graph":
        v = s_g
    else:  # combined
        v = (b * phi) + ((1.0 - b) * s_g)

    return round(max(0.0, min(1.0, v)), 4)


def compute_final_confidence(
    evidence_confidence: float,
    faithfulness_score: float,
    graph_consistency_score: Optional[float] = None,
    verify_mode: Optional[str] = None,
    beta: Optional[float] = None,
) -> Tuple[float, str]:
    """
    Compute final_confidence and determine confidence_tier.

    Returns:
    --------
    tuple of (final_confidence: float, confidence_tier: str)
    """
    w_e = settings.verification_w_evidence
    w_f = settings.verification_w_faithfulness

    v_score = compute_combined_verification_score(
        faithfulness_score=faithfulness_score,
        graph_consistency_score=graph_consistency_score,
        verify_mode=verify_mode,
        beta=beta,
    )

    final_score = round(w_e * evidence_confidence + w_f * v_score, 3)
    final_score = min(1.0, max(0.0, final_score))

    if final_score >= settings.verification_threshold_high:
        tier = "high"
    elif final_score >= settings.verification_threshold_medium:
        tier = "medium"
    else:
        tier = "low"

    logger.debug(
        "Computed final_confidence: %.3f (tier=%s, v_score=%.3f, faithfulness=%.3f, graph_consistency=%.3f)",
        final_score, tier, v_score, faithfulness_score, (graph_consistency_score or 1.0)
    )
    return final_score, tier
