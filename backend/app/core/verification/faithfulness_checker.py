"""
MedGraphRAG Backend — Step 8.2 Single-Pass Faithfulness Checker
=================================================================
Combines claim filtering and faithfulness verification into a SINGLE FAST LLM PASS.

Key Features & Optimizations:
  1. Pre-verification claim filtering:
     - Drops disclaimers ("This is information, not medical advice...")
     - Drops epistemic/meta statements ("The evidence does not mention...", "based on given evidence...")
     - Keeps max 4 factual claims (most important first).
  2. Payload snippet truncation: 400 chars per cited snippet.
  3. Single LLM call (max_tokens=250, temp=0.1) demanding strict JSON array.
  4. Returns tuple: (verifications: list[ClaimVerification], faithfulness_score: float, fallback_used: bool).
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

# Meta/epistemic patterns to filter out before claim verification
DISCARD_PATTERNS = [
    "this is information",
    "medical advice",
    "consult your physician",
    "consult a healthcare",
    "consult a physician",
    "the provided evidence does not",
    "the evidence provided does not",
    "does not specifically mention",
    "does not detail",
    "based on the given evidence",
    "i cannot provide",
    "i cannot confirm",
    "it cannot be concluded",
    "for specific treatment recommendations",
    "refer to current clinical practice",
    "refer to the full guideline",
    "the documents discuss",
]


def filter_answer_claims(answer_text: str, citations: List[CitationMeta]) -> List[Claim]:
    """
    Split answer_text into sentences and filter out disclaimers, epistemic meta-statements,
    and non-factual recommendation boilerplate.

    Returns at most 4 factual Claim objects.
    """
    all_cited_labels = [c.label for c in citations]
    raw_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer_text) if s.strip()]

    clean_claims: List[Claim] = []

    for sentence in raw_sentences:
        sent_lower = sentence.lower()
        if any(pat in sent_lower for pat in DISCARD_PATTERNS):
            continue

        cited_labels = re.findall(r"\[E\d+\]", sentence)
        if not cited_labels:
            cited_labels = all_cited_labels

        clean_claims.append(
            Claim(
                claim_text=sentence,
                cited_labels=cited_labels,
                claim_type="factual",
            )
        )
        if len(clean_claims) >= 4:
            break

    # If all sentences were meta/disclaimers, fallback to first non-disclaimer sentence
    if not clean_claims and raw_sentences:
        first_sent = raw_sentences[0]
        clean_claims.append(
            Claim(
                claim_text=first_sent[:300],
                cited_labels=all_cited_labels,
                claim_type="factual",
            )
        )

    return clean_claims


def verify_in_single_pass(
    answer_text: str,
    citations: List[CitationMeta],
    retrieval_result: Optional[RetrievalResult] = None,
) -> Tuple[List[ClaimVerification], float, bool]:
    """
    Perform claim filtering and single-pass faithfulness verification.

    Returns
    -------
    tuple of (verifications: list[ClaimVerification], faithfulness_score: float, fallback_used: bool)
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
                cited_snippets=[c.snippet[:400] for c in citations[:3]],
            )
            return [verification], 1.0, False

    # ── Step 2: Claim Filtering ──────────────────────────────────────────────
    claims = filter_answer_claims(answer_text, citations)

    # ── Filter Citations to CITED Labels Only ─────────────────────────────────
    cited_in_text = set(re.findall(r"\[E\d+\]", answer_text))
    target_citations = [c for c in citations if c.label in cited_in_text]

    if not target_citations:
        target_citations = citations[:3]

    # ── Build Evidence Text (400 chars max per snippet) ───────────────────────
    snippet_blocks = []
    for c in target_citations[:4]:
        snippet_text = c.snippet[:400].strip()
        snippet_blocks.append(f"{c.label}: {snippet_text}")
    evidence_text = "\n\n".join(snippet_blocks) if snippet_blocks else "No evidence provided."

    # Format claims text for prompt payload
    claims_text = "\n".join([f"Claim {i+1}: {c.claim_text}" for i, c in enumerate(claims)])
    prompt = (
        settings.verification_single_pass_prompt
        .replace("{evidence_text}", evidence_text)
        .replace("{answer_text}", claims_text)
    )
    messages = [{"role": "user", "content": prompt}]

    # ── Single-Pass LLM Call (max_tokens=250) ─────────────────────────────────
    max_tokens = settings.verification_max_tokens
    fallback_used = False

    try:
        llm_res = generate_chat(messages=messages, max_tokens=max_tokens, temperature=0.0)
        raw_text = llm_res.get("text", "").strip()

        # Extract JSON objects
        json_objects = re.findall(r"\{[^{}]*\}", raw_text)
        verifications: List[ClaimVerification] = []

        for i, raw_obj in enumerate(json_objects[: len(claims)]):
            try:
                item = json.loads(raw_obj)
                if isinstance(item, dict):
                    claim_obj = claims[i] if i < len(claims) else claims[0]
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
                    # Truncate explanation to 15 words per spec
                    words = explanation.split()
                    if len(words) > 15:
                        explanation = " ".join(words[:15])

                    snippets = [c.snippet[:200] for c in citations if c.label in claim_obj.cited_labels]

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
            logger.info("Single-pass verification complete: %d claims, score = %.3f (fallback_used=False)", len(verifications), score)
            return verifications, score, False

    except Exception as exc:
        logger.warning("Single-pass verification LLM call failed: %s. Using fallback.", exc)

    # ── Fallback Handling ────────────────────────────────────────────────────
    fallback_used = True
    fallback_claim = claims[0] if claims else Claim(claim_text=answer_text[:250].strip(), cited_labels=all_cited_labels, claim_type="factual")
    fallback_verification = ClaimVerification(
        claim=fallback_claim,
        verdict="not_mentioned",
        explanation="Single-pass verification parsing fallback.",
        cited_snippets=[c.snippet[:150] for c in citations[:2]],
    )
    return [fallback_verification], 0.5, True


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
