"""
MedGraphRAG Backend — Pipeline Entrypoint
==========================================
Unified end-to-end RAG pipeline entrypoint:
  Query -> Hybrid Retrieval -> Context Building -> LLM Chat Completion -> VerificationAgent -> VerifiedAnswerResult

This is the primary production entrypoint for MedGraphRAG.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.llm.generator import AnswerResult, GeneratorService
from app.core.retrieval.schemas import RetrievalRequest, RetrievalResult
from app.core.retrieval.service import HybridRetrievalService
from app.core.verification.schemas import VerifiedAnswerResult
from app.core.verification.verifier import VerificationAgent

logger = logging.getLogger(__name__)


class MedGraphRAGPipeline:
    """
    Unified production pipeline for MedGraphRAG.
    """

    def __init__(
        self,
        retrieval_service: Optional[HybridRetrievalService] = None,
        generator_service: Optional[GeneratorService] = None,
        verification_agent: Optional[VerificationAgent] = None,
    ) -> None:
        self.retrieval_service = retrieval_service or HybridRetrievalService()
        self.generator_service = generator_service or GeneratorService(retrieval_service=self.retrieval_service)
        self.verification_agent = verification_agent or VerificationAgent(
            generator_service=self.generator_service,
            retrieval_service=self.retrieval_service,
        )

    def answer(
        self,
        query: str,
        destination: str = "global",
    ) -> VerifiedAnswerResult:
        """
        Execute the full self-verifying MedGraphRAG pipeline for a given query.

        Parameters
        ----------
        query : str
            Natural language medical question.
        destination : str
            Target index destination (default 'global').

        Returns
        -------
        VerifiedAnswerResult
            Faithfulness-checked, confidence-scored answer result with complete provenance.
        """
        t_start = time.perf_counter()

        logger.info("Pipeline execution starting for query: %r (destination=%s)", query, destination)

        # ── Step 1: Hybrid Retrieval ─────────────────────────────────────────
        retrieval_req = RetrievalRequest(query=query, destination=destination)
        retrieval_res: RetrievalResult = self.retrieval_service.retrieve(retrieval_req)

        # ── Step 2: Generation ───────────────────────────────────────────────
        answer_res: AnswerResult = self.generator_service.generate(query=query, destination=destination)

        # ── Step 3: Verification & Gating ─────────────────────────────────────
        if settings.pipeline_verification_enabled:
            verified_res: VerifiedAnswerResult = self.verification_agent.verify(
                answer_result=answer_res,
                retrieval_result=retrieval_res,
            )
        else:
            conf = answer_res.evidence_confidence
            conf_tier = "high" if conf >= 0.7 else ("medium" if conf >= 0.5 else "low")
            verified_res = VerifiedAnswerResult(
                **answer_res.model_dump(),
                answer_status="verified",
                final_confidence=conf,
                confidence_tier=conf_tier,
                faithfulness_score=1.0,
                verification_ms=0.0,
                fallback_used=False,
                claim_verdicts=[],
                reasoning="Verification skipped via pipeline_verification_enabled=False.",
                retry_count=0,
            )

        total_ms = (time.perf_counter() - t_start) * 1000
        logger.info(
            "Pipeline execution complete in %.1f ms: status=%s, final_confidence=%.3f (%s)",
            total_ms, verified_res.answer_status, verified_res.final_confidence, verified_res.confidence_tier
        )

        return verified_res
