"""
MedGraphRAG Backend — Verification Agent (Step 8.2)
=====================================================
Orchestrates claim filtering, single-pass faithfulness checking, confidence scoring, and retry gating.

Ensures:
  - latency_total_ms equals sum(retrieval_ms, context_ms, llm_ms, verification_ms).
  - retry_count and fallback_used flags are tracked accurately.
  - Answers are confidence-scored and gated against hallucinations.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.llm.generator import AnswerResult, GeneratorService
from app.core.retrieval.schemas import RetrievalResult
from app.core.retrieval.service import HybridRetrievalService
from app.core.verification.confidence import compute_final_confidence
from app.core.verification.faithfulness_checker import verify_in_single_pass
from app.core.verification.retry_gate import RetryGate
from app.core.verification.schemas import ClaimVerification, VerifiedAnswerResult

logger = logging.getLogger(__name__)


class VerificationAgent:
    """
    Orchestrator for answer verification and confidence gating.
    """

    def __init__(
        self,
        generator_service: Optional[GeneratorService] = None,
        retrieval_service: Optional[HybridRetrievalService] = None,
    ) -> None:
        self.generator_service = generator_service or GeneratorService()
        self.retrieval_service = retrieval_service or HybridRetrievalService()
        self.retry_gate = RetryGate(
            generator_service=self.generator_service,
            retrieval_service=self.retrieval_service,
        )

    def verify(
        self,
        answer_result: AnswerResult,
        retrieval_result: RetrievalResult,
    ) -> VerifiedAnswerResult:
        """
        Verify answer faithfulness and gate output based on computed confidence.

        Parameters
        ----------
        answer_result : AnswerResult
            Output from GeneratorService.
        retrieval_result : RetrievalResult
            Output from HybridRetrievalService.

        Returns
        -------
        VerifiedAnswerResult object ready for user delivery.
        """
        t0 = time.perf_counter()

        # ── Edge Case: Malformed or Empty Answer ──────────────────────────────
        if not answer_result.answer_text or not answer_result.answer_text.strip():
            logger.error("Answer text is empty or malformed.")
            updated_lat = dict(answer_result.latency_breakdown)
            updated_lat["verification_ms"] = 0.0
            r_ms = updated_lat.get("retrieval_ms", 0.0)
            c_ms = updated_lat.get("context_ms", 0.0)
            l_ms = updated_lat.get("llm_ms", 0.0)
            updated_lat["total_ms"] = round(r_ms + c_ms + l_ms, 2)

            return VerifiedAnswerResult(
                query=answer_result.query,
                destination=answer_result.destination,
                answer_text="An error occurred while generating the response.",
                answer_status="error",
                final_confidence=0.0,
                confidence_tier="low",
                evidence_confidence=0.0,
                faithfulness_score=0.0,
                claims=[],
                citations=answer_result.citations,
                retry_count=0,
                retry_confidence_trajectory=[0.0],
                fallback_used=True,
                disclaimer="This is information, not medical advice — consult your physician.",
                n_evidence=answer_result.n_evidence,
                latency_breakdown=updated_lat,
                llm_mode=answer_result.llm_mode,
                ram_gb=answer_result.ram_gb,
                vram_mb=answer_result.vram_mb,
            )

        try:
            # ── Single-Pass Verification (Stage A + B) ────────────────────────
            verifications, faithfulness_score, fallback_used = verify_in_single_pass(
                answer_text=answer_result.answer_text,
                citations=answer_result.citations,
                retrieval_result=retrieval_result,
            )

            # ── Stage C: Compute Confidence ─────────────────────────────────
            final_confidence, tier = compute_final_confidence(
                evidence_confidence=answer_result.evidence_confidence,
                faithfulness_score=faithfulness_score,
            )

            verification_ms = (time.perf_counter() - t0) * 1000

            # Update latency breakdown and enforce exact sum
            updated_latency = dict(answer_result.latency_breakdown)
            updated_latency["verification_ms"] = round(verification_ms, 2)
            r_ms = updated_latency.get("retrieval_ms", 0.0)
            c_ms = updated_latency.get("context_ms", 0.0)
            l_ms = updated_latency.get("llm_ms", 0.0)
            v_ms = updated_latency["verification_ms"]
            updated_latency["total_ms"] = round(r_ms + c_ms + l_ms + v_ms, 2)

            has_contradiction = any(v.verdict == "contradicted" for v in verifications)
            is_refusal = any(v.verdict == "refusal_valid" for v in verifications)

            # ── Stage D: Gate or Trigger Retry ──────────────────────────────
            need_retry = (
                settings.verification_enabled
                and not is_refusal
                and (final_confidence < settings.verification_threshold_low or has_contradiction)
            )

            if need_retry:
                logger.info(
                    "Confidence (%.3f) below threshold or contradiction detected. Triggering RetryGate...",
                    final_confidence
                )
                return self.retry_gate.execute_retry_loop(
                    query=answer_result.query,
                    destination=answer_result.destination,
                    initial_answer=answer_result,
                    initial_retrieval=retrieval_result,
                    initial_claims=verifications,
                    initial_faithfulness=faithfulness_score,
                    initial_confidence=final_confidence,
                    initial_tier=tier,
                    initial_fallback_used=fallback_used,
                    start_time=t0,
                )

            # Assign Status
            if is_refusal:
                status = "refusal"
            elif has_contradiction:
                status = "contradiction_detected"
            elif final_confidence >= settings.verification_threshold_high:
                status = "verified"
            elif final_confidence >= settings.verification_threshold_medium:
                status = "caution"
            else:
                status = "uncertain"

            answer_text = answer_result.answer_text
            if status == "uncertain" and settings.uncertainty_disclosure.lower() not in answer_text.lower():
                answer_text = f"{settings.uncertainty_disclosure}{answer_text}"

            logger.info(
                "Verification complete: status=%s, final_confidence=%.3f (tier=%s, faithfulness=%.3f, verification_ms=%.1f, fallback_used=%s)",
                status, final_confidence, tier, faithfulness_score, verification_ms, fallback_used
            )

            return VerifiedAnswerResult(
                query=answer_result.query,
                destination=answer_result.destination,
                answer_text=answer_text,
                answer_status=status,
                final_confidence=final_confidence,
                confidence_tier=tier,
                evidence_confidence=answer_result.evidence_confidence,
                faithfulness_score=faithfulness_score,
                claims=verifications,
                citations=answer_result.citations,
                retry_count=0,
                retry_confidence_trajectory=[final_confidence],
                fallback_used=fallback_used,
                disclaimer="This is information, not medical advice — consult your physician.",
                n_evidence=answer_result.n_evidence,
                latency_breakdown=updated_latency,
                llm_mode=answer_result.llm_mode,
                ram_gb=answer_result.ram_gb,
                vram_mb=answer_result.vram_mb,
            )

        except Exception as exc:
            logger.error("Unhandled exception in VerificationAgent: %s. Returning fallback.", exc, exc_info=True)
            updated_lat = dict(answer_result.latency_breakdown)
            updated_lat["verification_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            r_ms = updated_lat.get("retrieval_ms", 0.0)
            c_ms = updated_lat.get("context_ms", 0.0)
            l_ms = updated_lat.get("llm_ms", 0.0)
            v_ms = updated_lat["verification_ms"]
            updated_lat["total_ms"] = round(r_ms + c_ms + l_ms + v_ms, 2)

            return VerifiedAnswerResult(
                query=answer_result.query,
                destination=answer_result.destination,
                answer_text=answer_result.answer_text,
                answer_status="error",
                final_confidence=answer_result.evidence_confidence,
                confidence_tier="medium",
                evidence_confidence=answer_result.evidence_confidence,
                faithfulness_score=0.5,
                claims=[],
                citations=answer_result.citations,
                retry_count=0,
                retry_confidence_trajectory=[answer_result.evidence_confidence],
                fallback_used=True,
                disclaimer="This is information, not medical advice — consult your physician.",
                n_evidence=answer_result.n_evidence,
                latency_breakdown=updated_lat,
                llm_mode=answer_result.llm_mode,
                ram_gb=answer_result.ram_gb,
                vram_mb=answer_result.vram_mb,
            )
