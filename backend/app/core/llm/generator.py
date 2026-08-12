"""
MedGraphRAG Backend — Generator Service
==========================================
End-to-end RAG Generation Pipeline:
  Query -> Retrieval -> Context Assembly -> LLM Chat Completion -> AnswerResult

Computes evidence confidence scoring from top evidence fused scores and source agreement.
Tracks end-to-end latency breakdowns and hardware memory (RAM/VRAM) metrics.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.config import settings
from app.core.context.context_builder import CitationMeta, ContextPackage, build_context
from app.core.llm.llm_loader import generate_chat, get_llm_mode
from app.core.retrieval.schemas import RetrievalRequest, RetrievalResult
from app.core.retrieval.service import HybridRetrievalService

logger = logging.getLogger(__name__)


class AnswerResult(BaseModel):
    """Full typed response from the end-to-end GeneratorService."""

    query: str = Field(description="Original user query.")
    destination: str = Field(description="Retrieval destination queried (default 'global').")
    answer_text: str = Field(description="Generated answer text from LLM.")
    citations: List[CitationMeta] = Field(description="List of cited evidence items and metadata.")
    evidence_confidence: float = Field(description="Computed evidence confidence score (0.0 - 1.0).")
    n_evidence: int = Field(description="Number of evidence items provided in context.")
    latency_breakdown: Dict[str, float] = Field(description="Detailed latency breakdown in ms.")
    llm_mode: str = Field(description="Active LLM mode ('full_gpu' | 'partial_gpu' | 'cpu').")
    ram_gb: float = Field(description="Process peak RAM usage in GB.")
    vram_mb: float = Field(description="CUDA VRAM allocation in MB.")


class GeneratorService:
    """
    Service orchestrator for end-to-end RAG generation.
    """

    def __init__(self, retrieval_service: Optional[HybridRetrievalService] = None) -> None:
        self.retrieval_service = retrieval_service or HybridRetrievalService()

    def generate(
        self,
        query: str,
        destination: str = "global",
        top_n: Optional[int] = None,
        category_filter: Optional[List[str]] = None,
    ) -> AnswerResult:
        """
        Execute full RAG pipeline for a given query.

        Parameters
        ----------
        query : str
            Natural language question.
        destination : str
            Target index destination (default 'global').
        top_n : int, optional
            Number of retrieval items to fetch.
        category_filter : list of str, optional
            Category restriction for retrieval.

        Returns
        -------
        AnswerResult object with generated answer, citations, confidence, and metrics.
        """
        t_start = time.perf_counter()
        latency_breakdown: Dict[str, float] = {}

        # ── Stage 1: Hybrid Retrieval ─────────────────────────────────────────
        t0 = time.perf_counter()
        retrieval_req = RetrievalRequest(
            query=query,
            destination=destination,
            top_n=top_n,
            category_filter=category_filter,
        )
        retrieval_res: RetrievalResult = self.retrieval_service.retrieve(retrieval_req)
        latency_breakdown["retrieval_ms"] = (time.perf_counter() - t0) * 1000

        # Copy over fine-grained retrieval latency breakdown
        for k, v in retrieval_res.latency_breakdown_ms.items():
            latency_breakdown[f"retrieval_{k}"] = v

        # ── Stage 2: Context Assembly ────────────────────────────────────────
        t0 = time.perf_counter()
        context_pkg: ContextPackage = build_context(retrieval_res)
        latency_breakdown["context_ms"] = (time.perf_counter() - t0) * 1000

        # ── Stage 3: LLM Generation ──────────────────────────────────────────
        messages = [
            {"role": "system", "content": context_pkg.system_prompt},
            {"role": "user", "content": context_pkg.user_prompt},
        ]

        llm_out = generate_chat(messages=messages)
        latency_breakdown["llm_ms"] = llm_out["latency_ms"]

        answer_text = llm_out["text"].strip()
        disclaimer = "This is information, not medical advice — consult your physician."
        if disclaimer.lower() not in answer_text.lower():
            answer_text = f"{answer_text}\n\n{disclaimer}"

        # ── Stage 4: Evidence Confidence Calculation ─────────────────────────
        confidence = self._compute_evidence_confidence(context_pkg.citations)

        total_ms = (time.perf_counter() - t_start) * 1000
        latency_breakdown["total_ms"] = total_ms

        logger.info(
            "RAG generation complete in %.1f ms (retrieval=%.1f ms, llm=%.1f ms, mode=%s, confidence=%.2f)",
            total_ms, latency_breakdown["retrieval_ms"], latency_breakdown["llm_ms"],
            llm_out["llm_mode"], confidence
        )

        return AnswerResult(
            query=query,
            destination=destination,
            answer_text=answer_text,
            citations=context_pkg.citations,
            evidence_confidence=confidence,
            n_evidence=context_pkg.n_evidence,
            latency_breakdown=latency_breakdown,
            llm_mode=llm_out["llm_mode"],
            ram_gb=llm_out["ram_gb"],
            vram_mb=llm_out["vram_mb"],
        )

    # -------------------------------------------------------------------------

    def _compute_evidence_confidence(self, citations: List[CitationMeta]) -> float:
        """
        Compute evidence confidence score from:
          (a) Mean fused score of included citations
          (b) Source/Category agreement (number of distinct categories supported)
        """
        if not citations:
            return 0.0

        # (a) Mean fused score (typically between 0.05 and 0.35 in RRF)
        mean_score = sum(c.fused_score for c in citations) / len(citations)
        # Normalise mean fused score into 0-1 scale (0.20+ is strong corroboration)
        score_norm = min(1.0, mean_score / 0.20)

        # (b) Source agreement (distinct categories)
        distinct_categories = len(set(c.category for c in citations))
        distinct_sources = len(set(c.source for c in citations))
        agreement = min(1.0, (distinct_categories + distinct_sources) / 4.0)

        w_fused = settings.confidence_weight_fused
        w_agree = settings.confidence_weight_agreement

        confidence = round(w_fused * score_norm + w_agree * agreement, 3)
        return min(1.0, max(0.0, confidence))
