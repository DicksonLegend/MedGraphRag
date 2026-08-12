"""
MedGraphRAG Backend — Context Builder
========================================
Assembles EvidenceItems from RetrievalResult into a token-budgeted prompt payload
with structured citation tags [E1], [E2], ... [En].

Responsibilities:
  1. Rank evidence items by fused_score descending.
  2. Format evidence items into structured prompt blocks with citation labels [E1], [E2], etc.
  3. Enforce token budget (config.context_max_tokens and config.evidence_max_per_prompt).
  4. Build citation metadata mapping (label -> provenance details).
  5. Format the complete system prompt instructions + evidence context.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.config import settings
from app.core.retrieval.schemas import EvidenceItem, RetrievalResult

logger = logging.getLogger(__name__)


class CitationMeta(BaseModel):
    """Provenance metadata for a single cited evidence item."""

    label: str = Field(description="Citation label used in context, e.g. '[E1]'.")
    chunk_id: str = Field(description="Unique chunk identifier.")
    document_id: str = Field(description="Parent document identifier.")
    source: str = Field(description="Source dataset folder.")
    category: str = Field(description="Document category.")
    chunk_type: str = Field(description="Chunk type.")
    title: Optional[str] = Field(default=None, description="Document title if present.")
    snippet: str = Field(description="Text snippet incorporated in the prompt.")
    fused_score: float = Field(description="Retrieval RRF fused score.")
    source_type: str = Field(description="Retrieval source ('faiss' | 'graph' | 'both').")


class ContextPackage(BaseModel):
    """Complete context package ready for LLM chat generation."""

    system_prompt: str = Field(description="System instructions for the LLM.")
    user_prompt: str = Field(description="Formatted user prompt including query and evidence blocks.")
    citations: List[CitationMeta] = Field(description="Citation lookup list for prompt evidence.")
    n_evidence: int = Field(description="Number of evidence items included in context.")
    estimated_tokens: int = Field(description="Estimated total token count of system + user prompts.")


def estimate_tokens(text: str) -> int:
    """
    Fast, heuristic token count estimation (~4 characters per token).
    Avoids tokenizer overhead during prompt construction.
    """
    return max(1, len(text) // 4)


def build_context(
    retrieval_result: RetrievalResult,
    max_evidence: Optional[int] = None,
    max_tokens: Optional[int] = None,
) -> ContextPackage:
    """
    Build a token-budgeted context package from RetrievalResult.

    Parameters
    ----------
    retrieval_result : RetrievalResult
        Output of HybridRetrievalService.retrieve().
    max_evidence : int, optional
        Override for maximum evidence items to include.
    max_tokens : int, optional
        Override for max estimated token budget for the context prompt payload.

    Returns
    -------
    ContextPackage containing system_prompt, user_prompt, citations, n_evidence, estimated_tokens.
    """
    max_ev = max_evidence or settings.evidence_max_per_prompt
    token_budget = max_tokens or settings.context_max_tokens

    # Sort evidence items by fused_score descending
    items = sorted(retrieval_result.items, key=lambda x: x.fused_score, reverse=True)

    citations: List[CitationMeta] = []
    evidence_blocks: List[str] = []

    accumulated_tokens = estimate_tokens(settings.system_prompt) + estimate_tokens(retrieval_result.query) + 50

    for idx, item in enumerate(items[:max_ev], start=1):
        label = f"[E{idx}]"
        snippet = item.text_snippet.strip()

        # Format individual evidence block
        header = f"{label} (Source: {item.source} | Category: {item.category} | Doc: {item.document_id})"
        if item.title:
            header += f" Title: {item.title}"

        block = f"{header}\n{snippet}"
        block_tokens = estimate_tokens(block)

        if accumulated_tokens + block_tokens > token_budget and len(evidence_blocks) > 0:
            logger.info(
                "Context token budget reached (%d / %d tokens). Truncating at %d evidence items.",
                accumulated_tokens, token_budget, len(evidence_blocks)
            )
            break

        accumulated_tokens += block_tokens
        evidence_blocks.append(block)

        citations.append(
            CitationMeta(
                label=label,
                chunk_id=item.chunk_id,
                document_id=item.document_id,
                source=item.source,
                category=item.category,
                chunk_type=item.chunk_type,
                title=item.title,
                snippet=snippet,
                fused_score=item.fused_score,
                source_type=item.source_type,
            )
        )

    # Construct user prompt with query and formatted evidence blocks
    if evidence_blocks:
        formatted_evidence = "\n\n".join(evidence_blocks)
        user_prompt = (
            f"EVIDENCE:\n{formatted_evidence}\n\n"
            f"QUESTION:\n{retrieval_result.query}\n\n"
            f"INSTRUCTIONS:\n"
            f"Answer the question based strictly on the provided evidence blocks [E1], [E2], etc. "
            f"Cite every factual statement using [E#]. If evidence is insufficient, state that clearly."
        )
    else:
        user_prompt = (
            f"QUESTION:\n{retrieval_result.query}\n\n"
            f"NOTE: No relevant evidence was found for this query."
        )

    total_tokens = estimate_tokens(settings.system_prompt) + estimate_tokens(user_prompt)

    logger.debug(
        "Built context package: %d evidence items, ~%d estimated tokens.",
        len(citations), total_tokens
    )

    return ContextPackage(
        system_prompt=settings.system_prompt,
        user_prompt=user_prompt,
        citations=citations,
        n_evidence=len(citations),
        estimated_tokens=total_tokens,
    )
