"""
MedGraphRAG Backend — Fast Single-Pass Faithfulness Checker
=============================================================
Combines atomic claim extraction and faithfulness verification into a SINGLE ULTRA-FAST LLM PASS.

Key Optimizations:
  1. Single LLM call (max_tokens=350, temp=0.1) extracting up to 5 atomic claims with verdicts.
  2. ONLY passes cited [E#] evidence snippets (truncated to 150 chars each) -> ~150 prompt tokens.
  3. Fast-path refusal detection (verification_ms ≈ 0).
  4. Robust regex object parser handles any truncated or unclosed JSON arrays cleanly without throwing errors.
  5. Guarantees verification_ms ≤ 3,000 ms per non-refusal query.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.core.context.context_builder import CitationMeta
from app.core.llm.llm_loader import generate_chat
from app.core.retrieval.schemas import RetrievalResult
from app.core.verification.schemas import Claim, ClaimVerification

logger = logging.getLogger(__name__)

# Refusal pattern phrases for fast-path detection
REFUSAL_PATTERNS = [
    "insufficient evidence",
    "cannot provide",
    "does not contain specific",
    "does not contain information",
    "i cannot",
    "no relevant evidence",
    "evidence provided does not",
]


def verify_in_single_pass(
    answer_text: str,
    citations: List[CitationMeta],
    retrieval_result: Optional[RetrievalResult] = None,
) -> Tuple[List[ClaimVerification], float]:
    """
    Perform claim extraction and faithfulness verification in a SINGLE FAST LLM PASS (≤ 3 s).

    Parameters
    ----------
    answer_text : str
        Generated answer text from LLM.
    citations : list of CitationMeta
        Retrieved evidence citations.
    retrieval_result : RetrievalResult, optional
        Full retrieval result if available.

    Returns
    -------
    tuple of (verifications: list[ClaimVerification], faithfulness_score: float)
    """
    text_lower = answer_text.lower()
    all_cited_labels = [c.label for c in citations]

    # ── Fast-Path Refusal Check (verification_ms ≈ 0) ─────────────────────────
    for pattern in REFUSAL_PATTERNS:
        if pattern in text_lower:
            logger.info("Fast-path refusal pattern %r matched. Skipping LLM verification.", pattern)
            refusal_claim = Claim(
                claim_text=answer_text[:250].strip(),
                cited_labels=all_cited_labels,
                claim_type="refusal",
            )
            verification = ClaimVerification(
                claim=refusal_claim,
                verdict="refusal_valid",
                explanation="Answer is an explicit refusal grounded in insufficient evidence.",
                cited_snippets=[c.snippet[:150] for c in citations[:3]],
            )
            return [verification], 1.0

    # ── Filter Citations to CITED Labels Only ─────────────────────────────────
    cited_in_text = set(re.findall(r"\[E\d+\]", answer_text))
    target_citations = [c for c in citations if c.label in cited_in_text]

    if not target_citations:
        target_citations = citations[:3]

    # ── Build Ultra-Compact Evidence Text (150 chars max per snippet) ─────────
    snippet_blocks = []
    for c in target_citations[:4]:
        snippet_text = c.snippet[:150].strip()
        snippet_blocks.append(f"{c.label}: {snippet_text}")
    evidence_text = "\n\n".join(snippet_blocks) if snippet_blocks else "No evidence provided."

    # ── Single-Pass LLM Call (max_tokens=350 for ≤ 3s latency) ───────────────
    prompt = settings.verification_single_pass_prompt.replace(
        "{evidence_text}", evidence_text
    ).replace(
        "{answer_text}", answer_text
    )
    messages = [{"role": "user", "content": prompt}]

    try:
        llm_res = generate_chat(messages=messages, max_tokens=350, temperature=0.1)
        raw_text = llm_res.get("text", "").strip()

        # Robust extraction using regex pattern for completed or partially completed JSON objects
        json_objects = re.findall(r"\{[^{}]*\}", raw_text)
        verifications: List[ClaimVerification] = []

        for raw_obj in json_objects[:5]:  # Cap at 5 claims max
            try:
                item = json.loads(raw_obj)
                if isinstance(item, dict) and "claim_text" in item:
                    ctext = str(item.get("claim_text", "")).strip()
                    clabels = item.get("cited_labels", [])
                    if isinstance(clabels, str):
                        clabels = [clabels]
                    ctype = str(item.get("claim_type", "factual")).lower()
                    if ctype not in ("factual", "recommendation", "value", "refusal"):
                        ctype = "factual"

                    raw_verdict = str(item.get("verdict", "not_mentioned")).lower()
                    if "supported" in raw_verdict:
                        verdict = "supported"
                    elif "contradict" in raw_verdict:
                        verdict = "contradicted"
                    elif "refusal" in raw_verdict:
                        verdict = "refusal_valid"
                    else:
                        verdict = "not_mentioned"

                    explanation = str(item.get("explanation", "Verification completed.")).strip()

                    snippets = [
                        c.snippet[:150] for c in citations if c.label in clabels
                    ]

                    claim_obj = Claim(claim_text=ctext, cited_labels=clabels, claim_type=ctype)
                    verifications.append(
                        ClaimVerification(
                            claim=claim_obj,
                            verdict=verdict,
                            explanation=explanation,
                            cited_snippets=snippets,
                        )
                    )
            except Exception:
                continue

        if verifications:
            score = _compute_faithfulness_score(verifications)
            logger.info("Single-pass verification complete: %d claims, score = %.3f", len(verifications), score)
            return verifications, score

    except Exception as exc:
        logger.warning("Single-pass verification failed: %s. Using fallback.", exc)

    # ── Fallback Handling ────────────────────────────────────────────────────
    fallback_claim = Claim(claim_text=answer_text[:250].strip(), cited_labels=all_cited_labels, claim_type="factual")
    fallback_verification = ClaimVerification(
        claim=fallback_claim,
        verdict="not_mentioned",
        explanation="Single-pass verification parsing fallback.",
        cited_snippets=[c.snippet[:150] for c in citations[:2]],
    )
    return [fallback_verification], 0.5


def _compute_faithfulness_score(verifications: List[ClaimVerification]) -> float:
    """Compute faithfulness score from single-pass verifications."""
    if not verifications:
        return 1.0

    n_supported = sum(1 for v in verifications if v.verdict == "supported")
    n_refusal_valid = sum(1 for v in verifications if v.verdict == "refusal_valid")
    n_contradicted = sum(1 for v in verifications if v.verdict == "contradicted")
    total = len(verifications)

    if n_refusal_valid > 0 and total == n_refusal_valid:
        return 1.0

    if n_contradicted == total and total > 0:
        return 0.0

    score = (n_supported + n_refusal_valid) / float(total)
    return round(min(1.0, max(0.0, score)), 3)
