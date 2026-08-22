#!/usr/bin/env python3
"""
MedGraphRAG — J1 Regression Suite
=================================
Runs the 5 golden queries P01–P05 through the retrieval engine,
serializes the exact chunk IDs, doc IDs, RRF fused scores, and computes SHA-256.
Can run in pre-build mode (evaluations/j1_regression_pre.json) or
post-build mode (evaluations/j1_regression_post.json).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

from app.core.retrieval.service import HybridRetrievalService
from app.core.retrieval.schemas import RetrievalRequest

GOLDEN_QUERIES: List[Dict[str, str]] = [
    {"id": "P01", "query": "warfarin INR monitoring guidelines atrial fibrillation"},
    {"id": "P02", "query": "ACE inhibitor hypertension treatment first line"},
    {"id": "P03", "query": "critical hemoglobin levels anemia transfusion threshold"},
    {"id": "P04", "query": "troponin elevation myocardial infarction diagnosis"},
    {"id": "P05", "query": "metformin type 2 diabetes contraindications renal failure"},
]


def run_regression_suite(output_path: Path) -> Dict[str, Any]:
    logger.info("Initializing HybridRetrievalService for regression run...")
    ret_svc = HybridRetrievalService()

    results: List[Dict[str, Any]] = []

    for item in GOLDEN_QUERIES:
        qid = item["id"]
        qtext = item["query"]
        logger.info("Running query %s: '%s' ...", qid, qtext)

        t0 = time.perf_counter()
        req = RetrievalRequest(query=qtext, destination="global", top_n=10)
        resp = ret_svc.retrieve(req)
        dur_ms = (time.perf_counter() - t0) * 1000

        retrieved_items = []
        for i, hit in enumerate(resp.items):
            retrieved_items.append({
                "rank": i + 1,
                "chunk_id": hit.chunk_id,
                "document_id": hit.document_id,
                "faiss_id": hit.faiss_id,
                "fused_score": round(hit.fused_score, 6),
                "faiss_score": round(hit.faiss_score, 6),
                "graph_score": round(hit.graph_score, 6),
                "source_type": hit.source_type,
                "category": hit.category,
                "chunk_type": hit.chunk_type,
                "graph_path_str": hit.graph_path_str,
            })

        results.append({
            "id": qid,
            "query": qtext,
            "latency_ms": round(dur_ms, 2),
            "entities_reached": resp.graph_stats.entities_reached,
            "chunks_from_graph": resp.graph_stats.chunks_from_graph,
            "top_doc_id": retrieved_items[0]["document_id"] if retrieved_items else None,
            "top_fused_score": retrieved_items[0]["fused_score"] if retrieved_items else None,
            "items_count": len(retrieved_items),
            "retrieved_items": retrieved_items,
        })

    # Strict deterministic serialization (sort_keys=True)
    serialized_bytes = json.dumps(results, indent=2, sort_keys=True).encode("utf-8")
    sha256_hash = hashlib.sha256(serialized_bytes).hexdigest()

    final_payload = {
        "suite": "J1 Golden Queries P01-P05 Regression Suite",
        "output_path": str(output_path),
        "sha256": sha256_hash,
        "p01_top_fused_score": results[0]["top_fused_score"] if results else None,
        "results": results,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_payload, f, indent=2, sort_keys=True)

    logger.info("Saved regression report → %s (SHA-256: %s)", output_path, sha256_hash)
    return final_payload


def main():
    parser = argparse.ArgumentParser(description="Run J1 Golden Queries Regression Suite")
    parser.add_argument("--phase", choices=["pre", "post"], default="pre", help="pre or post J1 build")
    parser.add_argument("--output", type=str, default=None, help="Custom output path")
    args = parser.parse_args()

    eval_dir = _PROJECT_ROOT / "evaluations"
    if args.output:
        out_fp = Path(args.output)
    else:
        out_fp = eval_dir / f"j1_regression_{args.phase}.json"

    payload = run_regression_suite(out_fp)
    print("\n" + "=" * 60)
    print(f"J1 REGRESSION {args.phase.upper()} SUMMARY")
    print("=" * 60)
    print(f"Artifact : {out_fp}")
    print(f"SHA-256  : {payload['sha256']}")
    print(f"P01 Score: {payload['p01_top_fused_score']}")
    for r in payload["results"]:
        print(f"  {r['id']}: top_score={r['top_fused_score']} | top_doc={r['top_doc_id']} | hits={r['items_count']}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
