#!/usr/bin/env python3
"""
MedGraphRAG — Comprehensive Baseline Evaluation Runner
=======================================================
Runs all baseline evaluations (retrieval + generation) and produces
a unified comparison report with statistical significance testing.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add backend to path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "backend"))

from evaluations.baselines.baseline_retrieval import run_baseline_comparison, print_summary
from evaluations.baselines.baseline_generation import run_generation_baselines, print_generation_summary

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def run_comprehensive_evaluation(
    retrieval_queries: Optional[List[str]] = None,
    generation_queries: Optional[List[str]] = None,
    top_n: int = 10,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Run comprehensive baseline evaluation across retrieval and generation.
    """
    if output_dir is None:
        output_dir = _PROJECT_ROOT / "evaluations" / "baselines" / "results"

    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")

    # 1. Retrieval Baselines
    logger.info("=" * 60)
    logger.info("PHASE 1: RETRIEVAL BASELINE EVALUATION")
    logger.info("=" * 60)

    retrieval_output = output_dir / f"retrieval_baselines_{timestamp}.json"
    retrieval_report = run_baseline_comparison(
        queries=retrieval_queries,
        top_n=top_n,
        output_path=retrieval_output,
    )
    print_summary(retrieval_report)

    # 2. Generation Baselines
    logger.info("=" * 60)
    logger.info("PHASE 2: GENERATION BASELINE EVALUATION")
    logger.info("=" * 60)

    generation_output = output_dir / f"generation_baselines_{timestamp}.json"
    generation_report = run_generation_baselines(
        queries=generation_queries,
        output_path=generation_output,
        include_verification=True,
    )
    print_generation_summary(generation_report)

    # 3. Combined Analysis
    combined_report = {
        "timestamp": timestamp,
        "retrieval": retrieval_report,
        "generation": generation_report,
        "comparative_analysis": analyze_combined(retrieval_report, generation_report),
    }

    combined_output = output_dir / f"comprehensive_baselines_{timestamp}.json"
    with open(combined_output, "w") as f:
        json.dump(combined_report, f, indent=2, default=str)

    logger.info("Comprehensive evaluation saved to: %s", combined_output)

    return combined_report


def analyze_combined(
    retrieval_report: Dict[str, Any],
    generation_report: Dict[str, Any],
) -> Dict[str, Any]:
    """Analyze combined retrieval + generation results."""
    analysis = {
        "retrieval_generation_correlation": {},
        "best_retriever_for_generation": None,
        "tradeoffs": {},
    }

    # Extract summary metrics
    retrieval_summary = retrieval_report.get("summary", {})
    generation_summary = generation_report.get("summary", {})

    # Find best retriever by different criteria
    best_latency = min(retrieval_summary.items(), key=lambda x: x[1].get("avg_latency_ms", float("inf"))) if retrieval_summary else None
    best_coverage = max(retrieval_summary.items(), key=lambda x: x[1].get("avg_items", 0)) if retrieval_summary else None
    best_graph = max(retrieval_summary.items(), key=lambda x: x[1].get("avg_graph_chunks", 0)) if retrieval_summary else None

    analysis["best_retriever_by_latency"] = best_latency[0] if best_latency else None
    analysis["best_retriever_by_coverage"] = best_coverage[0] if best_coverage else None
    analysis["best_retriever_by_graph_integration"] = best_graph[0] if best_graph else None

    # Tradeoff analysis
    analysis["tradeoffs"]["latency_vs_coverage"] = {
        name: {
            "latency_ms": metrics.get("avg_latency_ms", 0),
            "coverage": metrics.get("avg_items", 0),
            "graph_integration": metrics.get("avg_graph_chunks", 0),
        }
        for name, metrics in retrieval_summary.items()
    }

    analysis["tradeoffs"]["generation_latency_vs_confidence"] = {
        name: {
            "latency_ms": metrics.get("avg_latency_ms", 0),
            "confidence": metrics.get("avg_confidence", 0),
            "citations": metrics.get("avg_citations", 0),
        }
        for name, metrics in generation_summary.items()
    }

    # Key finding: MedGraphRAG vs baselines
    if "MedGraphRAG" in retrieval_summary and "BM25" in retrieval_summary:
        mg_latency = retrieval_summary["MedGraphRAG"].get("avg_latency_ms", 0)
        bm25_latency = retrieval_summary["BM25"].get("avg_latency_ms", 0)
        analysis["retrieval_generation_correlation"]["medgraph_vs_bm25_latency_ratio"] = mg_latency / bm25_latency if bm25_latency > 0 else 0

    return analysis


def print_comprehensive_summary(report: Dict[str, Any]) -> None:
    """Print formatted comprehensive evaluation summary."""
    print("\n" + "=" * 80)
    print("COMPREHENSIVE BASELINE EVALUATION SUMMARY")
    print("=" * 80)

    analysis = report.get("comparative_analysis", {})

    print("\n🏆 BEST RETRIEVERS:")
    print(f"  By Latency:        {analysis.get('best_retriever_by_latency', 'N/A')}")
    print(f"  By Coverage:       {analysis.get('best_retriever_by_coverage', 'N/A')}")
    print(f"  By Graph Integration: {analysis.get('best_retriever_by_graph_integration', 'N/A')}")

    print("\n⚖️  RETRIEVAL TRADEOFFS (Latency vs Coverage vs Graph):")
    for name, metrics in analysis.get("tradeoffs", {}).get("latency_vs_coverage", {}).items():
        print(f"  {name:30s} Latency: {metrics['latency_ms']:6.1f}ms | Items: {metrics['coverage']:4.1f} | Graph: {metrics['graph_integration']:4.1f}")

    print("\n⚖️  GENERATION TRADEOFFS (Latency vs Confidence vs Citations):")
    for name, metrics in analysis.get("tradeoffs", {}).get("generation_latency_vs_confidence", {}).items():
        print(f"  {name:35s} Latency: {metrics['latency_ms']:6.1f}ms | Conf: {metrics['confidence']:.3f} | Cites: {metrics['citations']:4.1f}")

    corr = analysis.get("retrieval_generation_correlation", {})
    if corr.get("medgraph_vs_bm25_latency_ratio"):
        print(f"\n📊 MedGraphRAG vs BM25 Latency Ratio: {corr['medgraph_vs_bm25_latency_ratio']:.2f}x")

    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Run comprehensive MedGraphRAG baseline evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full evaluation with default queries
  python -m evaluations.baselines.run_all_baselines

  # Run with custom queries
  python -m evaluations.baselines.run_all_baselines --queries "warfarin dosing" "sepsis treatment" "diabetes management"

  # Run only retrieval baselines
  python -m evaluations.baselines.run_all_baselines --retrieval-only

  # Run only generation baselines
  python -m evaluations.baselines.run_all_baselines --generation-only

  # Specify output directory
  python -m evaluations.baselines.run_all_baselines --output-dir evaluations/baselines/results
        """
    )

    parser.add_argument(
        "--queries", "-q",
        nargs="+",
        help="Custom queries for both retrieval and generation"
    )
    parser.add_argument(
        "--retrieval-queries", "-rq",
        nargs="+",
        help="Custom queries for retrieval only"
    )
    parser.add_argument(
        "--generation-queries", "-gq",
        nargs="+",
        help="Custom queries for generation only"
    )
    parser.add_argument(
        "--top-n", type=int,
        default=10,
        help="Top N results for retrieval"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        help="Output directory for results"
    )
    parser.add_argument(
        "--retrieval-only",
        action="store_true",
        help="Run only retrieval baselines"
    )
    parser.add_argument(
        "--generation-only",
        action="store_true",
        help="Run only generation baselines"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Debug logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    output_dir = Path(args.output_dir) if args.output_dir else None

    if args.retrieval_only:
        logger.info("Running RETRIEVAL ONLY evaluation")
        retrieval_report = run_baseline_comparison(
            queries=args.retrieval_queries,
            top_n=args.top_n,
            output_path=output_dir / f"retrieval_only_{time.strftime('%Y%m%d_%H%M%S')}.json" if output_dir else None,
        )
        print_summary(retrieval_report)
        return

    if args.generation_only:
        logger.info("Running GENERATION ONLY evaluation")
        generation_report = run_generation_baselines(
            queries=args.generation_queries,
            output_path=output_dir / f"generation_only_{time.strftime('%Y%m%d_%H%M%S')}.json" if output_dir else None,
        )
        print_generation_summary(generation_report)
        return

    # Run comprehensive evaluation
    report = run_comprehensive_evaluation(
        retrieval_queries=args.retrieval_queries or args.queries,
        generation_queries=args.generation_queries or args.queries,
        top_n=args.top_n,
        output_dir=output_dir,
    )

    print_comprehensive_summary(report)


if __name__ == "__main__":
    main()