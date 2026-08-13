"""
MedGraphRAG Backend — Agent Nodes
==================================
LangGraph Node handlers for:
  - router_node          : Runs Router Agent to classify intent
  - query_agent_node     : Executes standard RAG pipeline
  - knowledge_agent_node : Executes graph-first RAG pipeline
  - report_agent_node    : Stub handler for Step 10 report interpretation
  - out_of_scope_node    : Template refusal handler (0 ms, CPU only)
  - finalize_node        : Assembles final formatted response dictionary
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.agents.router import classify_intent
from app.core.agents.state import MedGraphState
from app.core.context.context_builder import build_context
from app.core.llm.generator import AnswerResult, GeneratorService
from app.core.pipeline import MedGraphRAGPipeline
from app.core.retrieval.schemas import RetrievalRequest, RetrievalResult
from app.core.retrieval.service import HybridRetrievalService
from app.core.verification.schemas import VerifiedAnswerResult
from app.core.verification.verifier import VerificationAgent

logger = logging.getLogger(__name__)

# Singletons shared across graph invocations
_pipeline: Optional[MedGraphRAGPipeline] = None
_retrieval_service: Optional[HybridRetrievalService] = None
_generator_service: Optional[GeneratorService] = None
_verification_agent: Optional[VerificationAgent] = None


def _get_pipeline() -> MedGraphRAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = MedGraphRAGPipeline()
    return _pipeline


def _get_services():
    global _retrieval_service, _generator_service, _verification_agent
    if _retrieval_service is None:
        _retrieval_service = HybridRetrievalService()
    if _generator_service is None:
        _generator_service = GeneratorService(retrieval_service=_retrieval_service)
    if _verification_agent is None:
        _verification_agent = VerificationAgent(
            generator_service=_generator_service,
            retrieval_service=_retrieval_service,
        )
    return _retrieval_service, _generator_service, _verification_agent


# ── Node 1: Router ────────────────────────────────────────────────────────────
def router_node(state: MedGraphState) -> Dict[str, Any]:
    """Classify user query intent into a target route."""
    query = state.get("query", "")
    report_payload = state.get("report_payload")

    route, mechanism, lat_ms = classify_intent(query=query, report_payload=report_payload)

    latency_ms = dict(state.get("latency_ms", {}))
    latency_ms["router"] = round(lat_ms, 2)

    logger.info("router_node: route=%s (mechanism=%s, latency=%.2f ms)", route, mechanism, lat_ms)
    return {"route": route, "latency_ms": latency_ms}


# ── Node 2: Query Agent (Standard RAG) ────────────────────────────────────────
def query_agent_node(state: MedGraphState) -> Dict[str, Any]:
    """Execute standard RAG pipeline via MedGraphRAGPipeline.answer()."""
    query = state.get("query", "")
    destination = state.get("destination", "global")

    logger.info("query_agent_node executing for query %r (destination=%s)", query, destination)
    pipeline = _get_pipeline()
    verified_res: VerifiedAnswerResult = pipeline.answer(query=query, destination=destination)

    return {"verified_result": verified_res}


# ── Node 3: Knowledge Agent (Graph-First RAG) ─────────────────────────────────
def knowledge_agent_node(state: MedGraphState) -> Dict[str, Any]:
    """Execute graph-first RAG pipeline using graph_store entity seeding and traversal."""
    query = state.get("query", "")
    destination = state.get("destination", "global")

    logger.info("knowledge_agent_node executing for query %r (destination=%s)", query, destination)
    ret_svc, gen_svc, verif_agent = _get_services()

    # Step A: Hybrid retrieval with expanded top_n for graph traversal
    retrieval_req = RetrievalRequest(query=query, destination=destination, top_n=12)
    retrieval_res: RetrievalResult = ret_svc.retrieve(retrieval_req)

    # Step B: Generate RAG answer
    answer_res: AnswerResult = gen_svc.generate(query=query, destination=destination, top_n=12)

    # Step C: Verification & Gating
    verified_res: VerifiedAnswerResult = verif_agent.verify(
        answer_result=answer_res,
        retrieval_result=retrieval_res,
    )

    return {"retrieval_result": retrieval_res, "verified_result": verified_res}


# ── Node 4: Report Agent (Step 10 Handler) ───────────────────────────────────
def report_agent_node(state: MedGraphState) -> Dict[str, Any]:
    """Execute Step 10 diagnostic lab report interpretation and private storage."""
    query = state.get("query", "Diagnostic Report Analysis")
    user_id = state.get("user_id") or "default_user"
    destination = state.get("destination", "private")
    report_payload = state.get("report_payload") or {}

    logger.info("report_agent_node processing payload for user %s (destination=%s)", user_id, destination)

    file_bytes = report_payload.get("file_bytes") or b""
    filename = report_payload.get("filename") or "report.txt"

    if not file_bytes and "raw_text" in report_payload:
        file_bytes = str(report_payload["raw_text"]).encode("utf-8")

    from app.core.report.service import ReportInterpretationService
    svc = ReportInterpretationService()

    try:
        report_res = svc.process_report(
            file_bytes=file_bytes,
            filename=filename,
            user_id=user_id,
            destination=destination,
        )

        lines: List[str] = []
        if report_res.critical_flag and report_res.escalation_text:
            lines.append(report_res.escalation_text)
            lines.append("")

        lines.append(f"### {report_res.parsed_summary}")
        lines.append("")
        lines.append("#### Laboratory Assessment & Explanations:")

        for idx, exp in enumerate(report_res.explanations, start=1):
            asm = exp.assessment
            nlv = asm.normalized_lab_value
            cls_upper = asm.classification.upper()
            status_symbol = "⚠️" if asm.is_critical else ("🔴" if "HIGH" in cls_upper or "LOW" in cls_upper else "🟢")
            lines.append(f"{idx}. {status_symbol} **{nlv.canonical_test_name}**: `{nlv.lab_value.value_raw_str} {nlv.lab_value.unit_raw}` ({cls_upper})")
            lines.append(f"   - **Ref Range**: {asm.reference_range_used}")
            lines.append(f"   - **Explanation**: {exp.what_it_means}")
            if exp.possible_causes:
                lines.append(f"   - **Possible Associated Conditions**: {', '.join(exp.possible_causes)}")
            if exp.provenance:
                lines.append(f"   - **Provenance**: {'; '.join(exp.provenance)}")
            lines.append("")

        lines.append(report_res.disclaimer)
        answer_text = "\n".join(lines)
        answer_status = "success"
        confidence = 1.0

    except Exception as e:
        logger.error("Report agent node execution failed: %s", e, exc_info=True)
        answer_text = (
            f"Error processing diagnostic report: {e}\n\n"
            "This is information, not medical advice — consult your physician."
        )
        answer_status = "error"
        confidence = 0.0

    verified_res = VerifiedAnswerResult(
        query=query,
        destination=destination,
        answer_text=answer_text,
        answer_status=answer_status,
        final_confidence=confidence,
        confidence_tier="high" if confidence > 0.8 else "low",
        evidence_confidence=1.0,
        faithfulness_score=1.0,
        claims=[],
        citations=[],
        retry_count=0,
        retry_confidence_trajectory=[confidence],
        fallback_used=False,
        disclaimer="This is information, not medical advice — consult your physician.",
        n_evidence=len(report_payload.get("lab_values", [])),
        latency_breakdown={"retrieval_ms": 0.0, "context_ms": 0.0, "llm_ms": 0.0, "verification_ms": 0.0, "total_ms": 0.0},
        llm_mode="full_gpu",
        ram_gb=0.0,
        vram_mb=0.0,
    )

    return {"verified_result": verified_res}


# ── Node 5: Out of Scope Node ────────────────────────────────────────────────
def out_of_scope_node(state: MedGraphState) -> Dict[str, Any]:
    """Template refusal for out-of-scope / non-medical queries (0 ms, CPU only)."""
    query = state.get("query", "")
    destination = state.get("destination", "global")

    logger.info("out_of_scope_node handling non-medical query %r", query)

    refusal_text = (
        "I am a specialized medical information assistant. "
        "I can only answer questions related to medical conditions, clinical guidelines, drug information, and lab tests. "
        "For general or non-medical inquiries, please consult an appropriate resource.\n\n"
        "This is information, not medical advice — consult your physician."
    )

    verified_res = VerifiedAnswerResult(
        query=query,
        destination=destination,
        answer_text=refusal_text,
        answer_status="out_of_scope",
        final_confidence=1.0,
        confidence_tier="high",
        evidence_confidence=1.0,
        faithfulness_score=1.0,
        claims=[],
        citations=[],
        retry_count=0,
        retry_confidence_trajectory=[1.0],
        fallback_used=False,
        disclaimer="This is information, not medical advice — consult your physician.",
        n_evidence=0,
        latency_breakdown={"retrieval_ms": 0.0, "context_ms": 0.0, "llm_ms": 0.0, "verification_ms": 0.0, "total_ms": 0.0},
        llm_mode="full_gpu",
        ram_gb=0.0,
        vram_mb=0.0,
    )

    return {"verified_result": verified_res}


# ── Node 6: Finalize Node ────────────────────────────────────────────────────
def finalize_node(state: MedGraphState) -> Dict[str, Any]:
    """Assemble final_response dictionary from state and verified_result."""
    verified: Optional[VerifiedAnswerResult] = state.get("verified_result")
    route = state.get("route", "medical_query")
    router_ms = state.get("latency_ms", {}).get("router", 0.0)

    graph_paths: List[str] = []
    citations_data: List[Dict[str, Any]] = []

    if verified and verified.citations:
        for c in verified.citations:
            citations_data.append(c.model_dump())
            if hasattr(c, "graph_paths") and c.graph_paths:
                graph_paths.extend(c.graph_paths)

    graph_paths = list(dict.fromkeys(graph_paths))

    r_ms = verified.latency_breakdown.get("retrieval_ms", 0.0) if verified else 0.0
    c_ms = verified.latency_breakdown.get("context_ms", 0.0) if verified else 0.0
    l_ms = verified.latency_breakdown.get("llm_ms", 0.0) if verified else 0.0
    v_ms = verified.latency_breakdown.get("verification_ms", 0.0) if verified else 0.0
    total_ms = round(router_ms + r_ms + c_ms + l_ms + v_ms, 2)

    final_response = {
        "route": route,
        "answer_text": verified.answer_text if verified else "",
        "answer_status": verified.answer_status if verified else "error",
        "confidence_tier": verified.confidence_tier if verified else "low",
        "final_confidence": verified.final_confidence if verified else 0.0,
        "citations": citations_data,
        "graph_paths": graph_paths,
        "disclaimer_present": (
            "consult your physician" in verified.answer_text.lower() if verified else False
        ),
        "retry_count": verified.retry_count if verified else 0,
        "latency_breakdown": {
            "router": router_ms,
            "retrieval": r_ms,
            "context": c_ms,
            "llm": l_ms,
            "verification": v_ms,
            "total": total_ms,
        },
    }

    logger.info("finalize_node complete for route=%s (total_ms=%.2f)", route, total_ms)
    return {"final_response": final_response}
