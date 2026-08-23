#!/usr/bin/env python3
"""
MedGraphRAG — Step J3 Relational Probe
=====================================
Evaluates top-5 candidate rankings under 'rrf' vs 'hybrid' for P01 (warfarin) and P05 (metformin).
Demonstrates rank shifts for chunks whose documents carry DRUG_TREATS/contraindication edges.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("j3_probe")

from app.core.retrieval.schemas import RetrievalRequest, RetrievalResult
from app.core.retrieval.service import HybridRetrievalService


def run_probe() -> Dict[str, Any]:
    svc = HybridRetrievalService()

    queries = {
        "P01_warfarin": "warfarin INR monitoring guidelines atrial fibrillation",
        "P05_metformin": "metformin type 2 diabetes contraindications renal failure",
    }

    probe_results: Dict[str, Any] = {}

    for q_key, q_text in queries.items():
        # 1. RRF mode (control)
        req_rrf = RetrievalRequest(query=q_text, destination="global", top_n=10)
        res_rrf = svc.retrieve(req_rrf)

        # 2. Hybrid mode (gamma=0.15)
        # We can temporarily patch or pass request
        # Since retrieve uses request.rerank_mode if present:
        setattr(req_rrf, "rerank_mode", "hybrid")
        setattr(req_rrf, "rerank_gamma", 0.15)
        res_hybrid = svc.retrieve(req_rrf)

        # Compare top-5 items
        rrf_top5 = [
            {
                "rank": i + 1,
                "chunk_id": item.chunk_id,
                "doc_id": item.document_id,
                "category": item.category,
                "fused_score": round(item.fused_score, 4),
            }
            for i, item in enumerate(res_rrf.items[:5])
        ]

        hybrid_top5 = [
            {
                "rank": i + 1,
                "chunk_id": item.chunk_id,
                "doc_id": item.document_id,
                "category": item.category,
                "fused_score": round(item.fused_score, 4),
            }
            for i, item in enumerate(res_hybrid.items[:5])
        ]

        # Compute rank shifts
        # Map chunk_id to rrf_rank
        rrf_ranks = {item.chunk_id: i + 1 for i, item in enumerate(res_rrf.items)}
        rank_shifts = []
        for h_rank, item in enumerate(res_hybrid.items[:5], start=1):
            r_rank = rrf_ranks.get(item.chunk_id, 99)
            shift = r_rank - h_rank  # positive means rose in rank
            rank_shifts.append({
                "chunk_id": item.chunk_id,
                "doc_id": item.document_id,
                "rrf_rank": r_rank if r_rank <= 10 else ">10",
                "hybrid_rank": h_rank,
                "rank_shift": f"+{shift}" if shift > 0 else (f"{shift}" if shift < 0 else "0"),
            })

        probe_results[q_key] = {
            "query": q_text,
            "rrf_top5": rrf_top5,
            "hybrid_top5": hybrid_top5,
            "rank_shifts": rank_shifts,
        }

    print("\n" + "=" * 80)
    print("STEP J3 RELATIONAL PROBE RANK-SHIFT TABLE")
    print("=" * 80)
    for q_key, data in probe_results.items():
        print(f"\nQuery [{q_key}]: '{data['query']}'")
        print("-" * 80)
        print(f"{'Hybrid Rank':<12} | {'RRF Rank':<10} | {'Shift':<8} | {'Chunk ID':<45} | Document ID")
        print("-" * 80)
        for s in data["rank_shifts"]:
            print(f"Rank {s['hybrid_rank']:<7} | Rank {str(s['rrf_rank']):<5} | {s['rank_shift']:<8} | {s['chunk_id'][:45]:<45} | {s['doc_id'][:35]}")

    print("=" * 80 + "\n")
    return probe_results


if __name__ == "__main__":
    run_probe()
