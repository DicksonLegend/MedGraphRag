"""
MedGraphRAG Backend — Clinical Query Rewriter & HyDE Module
============================================================
Distills long narrative clinical case vignettes (e.g. USMLE / MedQA vignettes)
into concise (<= 30 words), high-density search queries for MedCPT dense vector
embedding and Kuzu knowledge graph traversal.

Key Capabilities:
  1. Direct Clinical Vignette Rewriting: Extracts key clinical findings, abnormal labs/imaging,
     demographic risk factors, and differential diagnostic dilemmas.
  2. Deterministic: Uses Qwen2.5-7B-Instruct at T=0.0 with seed 42.
  3. Fail-Open: On any exception or model error, cleanly falls back to the raw query.
  4. Optional HyDE (Hypothetical Document Embeddings): Synthesizes a focused 1-paragraph clinical summary.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

REWRITE_SYSTEM_PROMPT = (
    "You are an expert clinical search specialist. Your task is to distill a detailed patient case vignette "
    "into a concise, high-density biomedical literature search query of at most 30 words.\n"
    "Extract and prioritize:\n"
    "1. Primary clinical findings and symptom timeline\n"
    "2. Crucial abnormal laboratory and imaging values\n"
    "3. Key differential diagnosis or therapeutic intervention sought\n\n"
    "Rules:\n"
    "- Output ONLY the concise search terms separated by spaces.\n"
    "- Do NOT include conversational filler, explanations, headings, option letters, or punctuation marks.\n"
    "- Strictly maximum 30 words."
)

HYDE_SYSTEM_PROMPT = (
    "You are an expert clinical professor. Given a medical question or patient vignette, write a concise "
    "1-paragraph hypothetical excerpt from an authoritative clinical guideline or medical textbook that "
    "directly answers the clinical dilemma and explains the underlying pathophysiological mechanism."
)


def rewrite_clinical_query(
    raw_query: str,
    max_words: int = 30,
    llm_instance: Optional[Any] = None,
) -> str:
    """
    Rewrite a narrative clinical vignette into a dense <=30-word retrieval query.

    Parameters
    ----------
    raw_query : str
        The raw patient vignette or clinical question.
    max_words : int
        Maximum number of words in the rewritten query (default 30).
    llm_instance : optional
        Optional llama_cpp.Llama instance if calling directly within an evaluation loop.

    Returns
    -------
    str
        Concise search query, or raw_query on fallback.
    """
    if not raw_query or not raw_query.strip():
        return raw_query

    # If query is already short (e.g. <= 15 words) and lacks narrative vignette structure, return as-is
    words = raw_query.strip().split()
    if len(words) <= getattr(settings, "query_rewrite_length_threshold", 25):
        # Unless it contains options text like "Options: A)"
        if "Options:" not in raw_query and "A)" not in raw_query:
            return raw_query

    t0 = time.perf_counter()
    try:
        # Clean options / instruction clutter from prompt for rewriting if present
        clean_prompt = raw_query
        if "Options:" in clean_prompt:
            clean_prompt = clean_prompt.split("Options:")[0].strip()
        if clean_prompt.lower().startswith("medical question:"):
            clean_prompt = clean_prompt[len("medical question:"):].strip()

        messages = [
            {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Patient case vignette:\n{clean_prompt}\n\nConcise search query (<= 30 words):",
            },
        ]

        if llm_instance is not None:
            out = llm_instance.create_chat_completion(
                messages=messages,
                max_tokens=60,
                temperature=0.0,
            )
            rewritten_text = out["choices"][0]["message"]["content"].strip()
        else:
            from app.core.llm.llm_loader import generate_chat
            gen_out = generate_chat(
                messages=messages,
                max_tokens=60,
                temperature=0.0,
            )
            rewritten_text = gen_out["text"].strip()

        # Clean any accidental quotes, markdown bolding, or newlines
        rewritten_text = re.sub(r'[\r\n]+', ' ', rewritten_text)
        rewritten_text = re.sub(r'["`*]', '', rewritten_text).strip()

        # Enforce maximum word count
        rewritten_words = rewritten_text.split()
        if len(rewritten_words) > max_words:
            rewritten_text = " ".join(rewritten_words[:max_words])

        dur_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "Query rewritten in %.1f ms: [%s] -> [%s]",
            dur_ms, raw_query[:60] + "...", rewritten_text
        )
        return rewritten_text if rewritten_text else raw_query

    except Exception as exc:
        logger.warning("Query rewriting failed (fail-open to raw query): %s", exc)
        return raw_query


def generate_hyde_query(
    raw_query: str,
    llm_instance: Optional[Any] = None,
) -> str:
    """
    Generate a Hypothetical Document Embeddings (HyDE) passage for vector search.

    Parameters
    ----------
    raw_query : str
        The raw patient vignette or clinical question.
    llm_instance : optional
        Optional llama_cpp.Llama instance.

    Returns
    -------
    str
        Synthesized hypothetical guideline passage, or raw_query on fallback.
    """
    if not raw_query or not raw_query.strip():
        return raw_query

    try:
        messages = [
            {"role": "system", "content": HYDE_SYSTEM_PROMPT},
            {"role": "user", "content": f"Clinical Question:\n{raw_query}\n\nHypothetical Guideline Passage:"},
        ]

        if llm_instance is not None:
            out = llm_instance.create_chat_completion(
                messages=messages,
                max_tokens=150,
                temperature=0.0,
            )
            hyde_text = out["choices"][0]["message"]["content"].strip()
        else:
            from app.core.llm.llm_loader import generate_chat
            gen_out = generate_chat(
                messages=messages,
                max_tokens=150,
                temperature=0.0,
            )
            hyde_text = gen_out["text"].strip()

        return hyde_text if hyde_text else raw_query

    except Exception as exc:
        logger.warning("HyDE generation failed (fail-open to raw query): %s", exc)
        return raw_query
