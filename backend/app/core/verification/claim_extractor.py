"""
MedGraphRAG Backend — Claim Extractor
========================================
Extracts atomic factual claims from generated answer text.

Optimizations & Fallbacks:
  - Fast-path refusal detection: skips LLM call if answer is an explicit refusal,
    saving ~5s latency.
  - JSON parse error fallback: treats entire answer as a single claim if parsing fails.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.context.context_builder import CitationMeta
from app.core.llm.llm_loader import generate_chat
from app.core.verification.schemas import Claim

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


def extract_claims(
    answer_text: str,
    citations: List[CitationMeta],
) -> List[Claim]:
    """
    Extract atomic factual claims from answer_text.

    Parameters
    ----------
    answer_text : str
        Generated answer text from LLM.
    citations : list of CitationMeta
        Retrieved evidence citations.

    Returns
    -------
    list of Claim objects
    """
    all_cited_labels = [c.label for c in citations]
    text_lower = answer_text.lower()

    # ── Fast-path: Refusal pattern check ─────────────────────────────────────
    for pattern in REFUSAL_PATTERNS:
        if pattern in text_lower:
            logger.info(
                "Refusal pattern %r matched in answer text. Skipping LLM claim extraction.",
                pattern
            )
            return [
                Claim(
                    claim_text=answer_text[:300].strip(),
                    cited_labels=all_cited_labels,
                    claim_type="refusal",
                )
            ]

    # ── LLM-based Claim Extraction ───────────────────────────────────────────
    prompt = settings.verification_claim_extraction_prompt.replace("{answer_text}", answer_text)
    messages = [{"role": "user", "content": prompt}]

    try:
        llm_res = generate_chat(messages=messages, max_tokens=400, temperature=0.0)
        raw_output = llm_res.get("text", "").strip()

        # Extract JSON array string
        json_match = re.search(r"\[.*\]", raw_output, re.DOTALL)
        if json_match:
            raw_json = json_match.group(0)
            data = json.loads(raw_json)

            claims: List[Claim] = []
            for item in data:
                if isinstance(item, dict) and "claim_text" in item:
                    ctext = str(item.get("claim_text", "")).strip()
                    clabels = item.get("cited_labels", [])
                    if isinstance(clabels, str):
                        clabels = [clabels]
                    ctype = str(item.get("claim_type", "factual")).lower()
                    if ctype not in ("factual", "recommendation", "value", "refusal"):
                        ctype = "factual"

                    # If labels are missing in item, infer from ctext via regex [E#]
                    if not clabels:
                        clabels = re.findall(r"\[E\d+\]", ctext)

                    if ctext:
                        claims.append(
                            Claim(
                                claim_text=ctext,
                                cited_labels=clabels,
                                claim_type=ctype,
                            )
                        )

            if claims:
                logger.info("Extracted %d atomic claims from answer text.", len(claims))
                return claims

    except Exception as exc:
        logger.warning("LLM claim extraction failed / parse error: %s. Using fallback.", exc)

    # ── Graceful Fallback: Treat entire answer as single claim ──────────────
    logger.info("Using single-claim fallback for answer text.")
    return [
        Claim(
            claim_text=answer_text[:500].strip(),
            cited_labels=all_cited_labels,
            claim_type="factual",
        )
    ]
