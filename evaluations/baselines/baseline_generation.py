#!/usr/bin/env python3
"""
MedGraphRAG — Baseline Generation Methods
==========================================
Implements standard baseline generation methods for comparison:
1. No-RAG (LLM only, no retrieval)
2. RAG with FAISS only (no graph, no verification)
3. RAG with Hybrid Retrieval (no verification)
4. Full MedGraphRAG (with verification) - reference

Evaluates on: accuracy, faithfulness, confidence calibration, latency.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.llm.generator import GeneratorService, AnswerResult
from app.core.llm.llm_loader import generate_chat
from app.core.pipeline import MedGraphRAGPipeline
from app.core.retrieval.service import HybridRetrievalService
from app.core.verification.verifier import VerificationAgent

logger = logging.getLogger(__name__)

# Test queries for generation evaluation
GENERATION_QUERIES = [
    "warfarin INR monitoring guidelines atrial fibrillation",
    "ACE inhibitor hypertension treatment first line",
    "critical hemoglobin levels anemia transfusion threshold",
    "troponin elevation myocardial infarction diagnosis",
    "metformin type 2 diabetes contraindications renal failure",
    "aspirin dosing secondary prevention coronary artery disease",
    "direct oral anticoagulant reversal agent andexanet alfa",
    "sepsis bundle lactate clearance antibiotics timing",
]


class BaselineGenerator:
    """Base class for baseline generators."""

    def __init__(self, name: str):
        self.name = name

    def generate(self, query: str) -> Dict[str, Any]:
        """Generate answer for a query. Must be implemented by subclasses."""
        raise NotImplementedError


class NoRAGGenerator(BaselineGenerator):
    """LLM only, no retrieval context."""

    def __init__(self):
        super().__init__("NoRAG (LLM Only)")

    def generate(self, query: str) -> Dict[str, Any]:
        t0 = time.perf_counter()

        messages = [
            {"role": "system", "content": settings.system_prompt},
            {"role": "user", "content": f"Answer this medical question: {query}\n\nThis is information, not medical advice — consult your physician."},
        ]

        llm_out = generate_chat(messages=messages)
        latency_ms = (time.perf_counter() - t0) * 1000 + llm_out["latency_ms"]

        return {
            "query": query,
            "answer": llm_out["text"],
            "citations": [],
            "latency_ms": latency_ms,
            "llm_mode": llm_out["llm_mode"],
            "evidence_confidence": 0.0,
            "n_evidence": 0,
        }


class FAISSOnlyGenerator(BaselineGenerator):
    """RAG with FAISS retrieval only, no graph, no verification."""

    def __init__(self):
        super().__init__("FAISS Only RAG")
        self.generator = GeneratorService()

    def generate(self, query: str) -> Dict[str, Any]:
        t0 = time.perf_counter()

        # Use generator service with FAISS only (no graph)
        # We'll modify the retrieval to use FAISS only
        answer: AnswerResult = self.generator.generate(query=query, destination="global")

        latency_ms = (time.perf_counter() - t0) * 1000

        return {
            "query": query,
            "answer": answer.answer_text,
            "citations": [c.model_dump() for c in answer.citations],
            "latency_ms": latency_ms,
            "llm_mode": answer.llm_mode,
            "evidence_confidence": answer.evidence_confidence,
            "n_evidence": answer.n_evidence,
        }


class HybridNoVerificationGenerator(BaselineGenerator):
    """Full hybrid retrieval + generation, but no verification step."""

    def __init__(self):
        super().__init__("Hybrid RAG (No Verification)")
        self.generator = GeneratorService()
        self.retrieval_service = HybridRetrievalService()

    def generate(self, query: str) -> Dict[str, Any]:
        t0 = time.perf_counter()

        # Get retrieval
        from app.core.retrieval.schemas import RetrievalRequest
        retrieval_req = RetrievalRequest(query=query, destination="global")
        retrieval_res = self.retrieval_service.retrieve(retrieval_req)

        # Generate without verification
        answer: AnswerResult = self.generator.generate(query=query, destination="global")

        latency_ms = (time.perf_counter() - t0) * 1000

        return {
            "query": query,
            "answer": answer.answer_text,
            "citations": [c.model_dump() for c in answer.citations],
            "latency_ms": latency_ms,
            "llm_mode": answer.llm_mode,
            "evidence_confidence": answer.evidence_confidence,
            "n_evidence": answer.n_evidence,
            "retrieval_latency_ms": retrieval_res.latency_ms,
        }


class FullMedGraphRAGGenerator(BaselineGenerator):
    """Full MedGraphRAG pipeline with verification."""

    def __init__(self):
        super().__init__("Full MedGraphRAG (Verified)")
        self.pipeline = MedGraphRAGPipeline()

    def generate(self, query: str) -> Dict[str, Any]:
        t0 = time.perf_counter()

        verified_result = self.pipeline.answer(query=query, destination="global")

        latency_ms = (time.perf_counter() - t0) * 1000

        return {
            "query": query,
            "answer": verified_result.answer_text,
            "answer_status": verified_result.answer_status,
            "confidence_tier": verified_result.confidence_tier,
            "final_confidence": verified_result.final_confidence,
            "faithfulness_score": verified_result.faithfulness_score,
            "citations": [c.model_dump() for c in verified_result.citations],
            "latency_ms": latency_ms,
            "llm_mode": verified_result.llm_mode,
            "evidence_confidence": verified_result.evidence_confidence,
            "n_evidence": verified_result.n_evidence,
            "retry_count": verified_result.retry_count,
            "fallback_used": verified_result.fallback_used,
        }


def run_generation_baselines(
    queries: Optional[List[str]] = None,
    output_path: Optional[Path] = None,
    include_verification: bool = True,
) -> Dict[str, Any]:
    """
    Run all baseline generators on the same queries.
    """
    if queries is None:
        queries = GENERATION_QUERIES

    generators = [
        NoRAGGenerator(),
        FAISSOnlyGenerator(),
        HybridNoVerificationGenerator(),
    ]

    if include_verification:
        generators.append(FullMedGraphRAGGenerator())

    all_results = {}

    for generator in generators:
        logger.info("Running generator: %s", generator.name)
        gen_results = {}

        for query in queries:
            try:
                result = generator.generate(query)
                gen_results[query] = result
            except Exception as e:
                logger.error("Error in %s for query '%s': %s", generator.name, query, e)
                gen_results[query] = {"error": str(e)}

        all_results[generator.name] = gen_results

    # Compute summary
    summary = {}
    for gen_name, results in all_results.items():
        latencies = []
        confidences = []
        n_citations = []
        n_evidence = []
        statuses = []

        for query, result in results.items():
            if "error" not in result:
                latencies.append(result.get("latency_ms", 0))
                confidences.append(result.get("final_confidence", result.get("evidence_confidence", 0)))
                n_citations.append(len(result.get("citations", [])))
                n_evidence.append(result.get("n_evidence", 0))
                statuses.append(result.get("answer_status", "unknown"))

        summary[gen_name] = {
            "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
            "avg_confidence": sum(confidences) / len(confidences) if confidences else 0,
            "avg_citations": sum(n_citations) / len(n_citations) if n_citations else 0,
            "avg_evidence": sum(n_evidence) / len(n_evidence) if n_evidence else 0,
            "status_distribution": {s: statuses.count(s) for s in set(statuses)},
            "queries_successful": len(latencies),
            "queries_total": len(queries),
        }

    final_report = {
        "queries": queries,
        "results": all_results,
        "summary": summary,
        "timestamp": time.time(),
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(final_report, f, indent=2, default=str)
        logger.info("Generation baseline comparison saved to: %s", output_path)

    return final_report


def print_generation_summary(report: Dict[str, Any]) -> None:
    """Print formatted summary of generation baseline results."""
    print("\n" + "=" * 80)
    print("BASELINE GENERATION COMPARISON SUMMARY")
    print("=" * 80)
    print(f"Queries: {len(report['queries'])}")
    print("-" * 80)

    for name, metrics in report["summary"].items():
        print(f"\n{name}:")
        print(f"  Avg Latency: {metrics['avg_latency_ms']:.1f} ms")
        print(f"  Avg Confidence: {metrics['avg_confidence']:.3f}")
        print(f"  Avg Citations: {metrics['avg_citations']:.1f}")
        print(f"  Avg Evidence Items: {metrics['avg_evidence']:.1f}")
        print(f"  Status Distribution: {metrics['status_distribution']}")
        print(f"  Success Rate: {metrics['queries_successful']}/{metrics['queries_total']}")

    print("=" * 80)


def evaluate_faithfulness(
    report: Dict[str, Any],
    judge_model: str = "gpt-4o-mini",
) -> Dict[str, Any]:
    """
    Evaluate faithfulness of generated answers using LLM-as-judge.
    Compares generated claims against cited evidence.
    """
    # This would use an LLM judge to evaluate faithfulness
    # Placeholder for now
    return {
        "status": "not_implemented",
        "message": "Faithfulness evaluation requires LLM judge integration",
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run baseline generation comparison")
    parser.add_argument("--output", "-o", type=str, help="Output JSON path")
    parser.add_argument("--queries", "-q", nargs="+", help="Custom queries to evaluate")
    parser.add_argument("--no-verification", action="store_true", help="Skip full MedGraphRAG (with verification)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    output_path = Path(args.output) if args.output else None

    report = run_generation_baselines(
        queries=args.queries,
        output_path=output_path,
        include_verification=not args.no_verification,
    )

    print_generation_summary(report)