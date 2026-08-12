"""
MedGraphRAG Backend — Retry Gate
==================================
Gates low-confidence or contradicted answers through intelligent, failure-mode-aware retries.

Key Features & Optimizations:
  1. Failure-mode-aware routing:
     - Low evidence_confidence (<0.5) -> Re-retrieve with top_k x 1.5.
     - Low faithfulness_score (<0.5) -> Skip re-retrieval; re-generate with strict_system_prompt.
  2. Early stopping: breaks retry loop if |confidence_new - confidence_prev| < early_stop_delta (0.05).
  3. Latency budget guard: stops retries if elapsed time approaches query_latency_budget_ms (12,000 ms).
  4. Keeps best answer across attempts and prepends uncertainty disclosure if confidence remains low.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.context.context_builder import CitationMeta, ContextPackage, build_context
from app.core.llm.generator import AnswerResult, GeneratorService
from app.core.llm.llm_loader import generate_chat
from app.core.retrieval.schemas import RetrievalRequest, RetrievalResult
from app.core.retrieval.service import HybridRetrievalService
from app.core.verification.confidence import compute_final_confidence
from app.core.verification.faithfulness_checker import verify_in_single_pass
from app.core.verification.schemas import ClaimVerification, VerifiedAnswerResult

logger = logging.getLogger(__name__)


class RetryGate:
    """
    Intelligent Retry Gate for RAG pipeline answers.
    """

    def __init__(
        self,
        generator_service: Optional[GeneratorService] = None,
        retrieval_service: Optional[HybridRetrievalService] = None,
    ) -> None:
        self.generator_service = generator_service or GeneratorService()
        self.retrieval_service = retrieval_service or HybridRetrievalService()

    def execute_retry_loop(
        self,
        query: str,
        destination: str,
        initial_answer: AnswerResult,
        initial_retrieval: RetrievalResult,
        initial_claims: List[ClaimVerification],
        initial_faithfulness: float,
        initial_confidence: float,
        initial_tier: str,
        start_time: float,
    ) -> VerifiedAnswerResult:
        """
        Execute intelligent retry attempts bounded by max_retries, early_stop_delta, and latency budget.
        """
        max_retries = settings.verification_max_retries
        early_stop_delta = settings.early_stop_delta
        latency_budget_ms = settings.query_latency_budget_ms

        best_answer: AnswerResult = initial_answer
        best_retrieval: RetrievalResult = initial_retrieval
        best_claims: List[ClaimVerification] = initial_claims
        best_faithfulness: float = initial_faithfulness
        best_confidence: float = initial_confidence
        best_tier: str = initial_tier

        trajectory: List[float] = [initial_confidence]
        prev_confidence: float = initial_confidence

        logger.info(
            "Executing RetryGate loop for query %r (initial_confidence=%.3f, max_retries=%d)",
            query, initial_confidence, max_retries
        )

        for attempt in range(1, max_retries + 1):
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            if elapsed_ms >= 5000.0:
                logger.info(
                    "Elapsed query time (%.1f ms) reached 5s cap. Skipping retry to guarantee total latency budget < 12s.",
                    elapsed_ms
                )
                break

            # Determine Failure Mode
            low_evidence = best_answer.evidence_confidence < 0.50
            low_faithfulness = best_faithfulness < 0.50

            retry_answer: AnswerResult
            retry_retrieval: RetrievalResult

            if low_evidence:
                # Mode A: Retrieval failure -> re-retrieve with expanded top_k
                top_k = int(settings.retrieval_top_n * (1.0 + 0.5 * attempt))
                logger.info("Retry attempt %d/%d (Mode: Low Evidence): re-retrieving with top_k=%d...", attempt, max_retries, top_k)

                retry_retrieval = self.retrieval_service.retrieve(
                    RetrievalRequest(query=query, destination=destination, top_n=top_k)
                )
                retry_answer = self.generator_service.generate(
                    query=query, destination=destination, top_n=top_k
                )

            elif low_faithfulness:
                # Mode B: Generation grounding failure -> re-generate with strict_system_prompt (skip re-retrieval)
                logger.info("Retry attempt %d/%d (Mode: Low Faithfulness): re-generating with strict system prompt...", attempt, max_retries)
                retry_retrieval = best_retrieval

                context_pkg: ContextPackage = build_context(retry_retrieval)
                messages = [
                    {"role": "system", "content": settings.strict_system_prompt},
                    {"role": "user", "content": context_pkg.user_prompt},
                ]
                llm_out = generate_chat(messages=messages)
                answer_text = llm_out["text"].strip()
                disclaimer = "This is information, not medical advice — consult your physician."
                if disclaimer.lower() not in answer_text.lower():
                    answer_text = f"{answer_text}\n\n{disclaimer}"

                retry_answer = AnswerResult(
                    query=query,
                    destination=destination,
                    answer_text=answer_text,
                    citations=context_pkg.citations,
                    evidence_confidence=best_answer.evidence_confidence,
                    n_evidence=context_pkg.n_evidence,
                    latency_breakdown={"llm_ms": llm_out["latency_ms"]},
                    llm_mode=llm_out["llm_mode"],
                    ram_gb=llm_out["ram_gb"],
                    vram_mb=llm_out["vram_mb"],
                )
            else:
                # General retry
                top_k = int(settings.retrieval_top_n * (1.0 + 0.5 * attempt))
                retry_retrieval = self.retrieval_service.retrieve(
                    RetrievalRequest(query=query, destination=destination, top_n=top_k)
                )
                retry_answer = self.generator_service.generate(
                    query=query, destination=destination, top_n=top_k
                )

            # Re-verify in single-pass
            retry_claims, retry_faithfulness = verify_in_single_pass(
                answer_text=retry_answer.answer_text,
                citations=retry_answer.citations,
                retrieval_result=retry_retrieval,
            )

            retry_confidence, retry_tier = compute_final_confidence(
                evidence_confidence=retry_answer.evidence_confidence,
                faithfulness_score=retry_faithfulness,
            )

            trajectory.append(retry_confidence)
            delta = abs(retry_confidence - prev_confidence)

            logger.info(
                "Retry attempt %d result: final_confidence=%.3f (tier=%s, delta=%.3f)",
                attempt, retry_confidence, retry_tier, delta
            )

            if retry_confidence > best_confidence:
                best_answer = retry_answer
                best_retrieval = retry_retrieval
                best_claims = retry_claims
                best_faithfulness = retry_faithfulness
                best_confidence = retry_confidence
                best_tier = retry_tier

            # Early Stopping Check
            if delta < early_stop_delta:
                logger.info("Early stopping retry loop: confidence change (%.3f -> %.3f) is below delta %.2f.", prev_confidence, retry_confidence, early_stop_delta)
                break

            prev_confidence = retry_confidence

            # Exit if threshold reached and no contradictions
            has_contradiction = any(c.verdict == "contradicted" for c in retry_claims)
            if retry_confidence >= settings.verification_threshold_medium and not has_contradiction:
                logger.info("Retry successful on attempt %d! Confidence reached %.3f (%s).", attempt, retry_confidence, retry_tier)
                break

        # ── Final Status Determination ───────────────────────────────────────
        has_contradictions = any(c.verdict == "contradicted" for c in best_claims)
        is_refusal = any(c.verdict == "refusal_valid" for c in best_claims)

        answer_text = best_answer.answer_text

        if is_refusal:
            status = "refusal"
        elif has_contradictions:
            status = "contradiction_detected"
            if settings.contradiction_warning.lower() not in answer_text.lower():
                answer_text = f"{settings.contradiction_warning}\n\n{answer_text}"
        elif best_confidence >= settings.verification_threshold_high:
            status = "verified"
        elif best_confidence >= settings.verification_threshold_medium:
            status = "caution"
        else:
            status = "uncertain"
            if settings.uncertainty_disclosure.lower() not in answer_text.lower():
                answer_text = f"{settings.uncertainty_disclosure}{answer_text}"

        return VerifiedAnswerResult(
            query=query,
            destination=destination,
            answer_text=answer_text,
            answer_status=status,
            final_confidence=best_confidence,
            confidence_tier=best_tier,
            evidence_confidence=best_answer.evidence_confidence,
            faithfulness_score=best_faithfulness,
            claims=best_claims,
            citations=best_answer.citations,
            retry_count=len(trajectory) - 1,
            retry_confidence_trajectory=trajectory,
            disclaimer="This is information, not medical advice — consult your physician.",
            n_evidence=best_answer.n_evidence,
            latency_breakdown=best_answer.latency_breakdown,
            llm_mode=best_answer.llm_mode,
            ram_gb=best_answer.ram_gb,
            vram_mb=best_answer.vram_mb,
        )
