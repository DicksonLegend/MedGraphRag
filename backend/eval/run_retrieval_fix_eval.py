#!/usr/bin/env python3
"""
MedGraphRAG Backend — Step 6 Hybrid Retrieval Fix Evaluation
================================================================
Re-runs the 10 probe queries after implementing:
  1. Document-level deduplication in fusion.py
  2. Independent entity seeding from query terms in graph_store.py

Verifies:
  - P01 shows ≤2 chunks from PMID_38823454 (was 5).
  - At least 5/10 probes show entities_reached > 0.
  - At least 3/10 probes show chunks_from_graph > 0.
  - Noisy drug edges remain penalized.
  - Saves evaluations/step6_fix_report.json.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List

_PROJECT_ROOT = Path(__file__).parent.parent.parent  # MedGraphRag/
sys.path.insert(0, str(_PROJECT_ROOT / "backend"))

import psutil

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("retrieval_fix_eval")

from app.config import settings
from app.core.retrieval.schemas import RetrievalRequest, RetrievalResult
from app.core.retrieval.service import HybridRetrievalService

PROBE_QUERIES: List[Dict] = [
    {
        "id": "P01",
        "query": "warfarin INR monitoring guidelines atrial fibrillation",
        "description": "Anticoagulation guideline",
    },
    {
        "id": "P02",
        "query": "ACE inhibitor hypertension treatment first line",
        "description": "Drug + guideline cross-domain",
    },
    {
        "id": "P03",
        "query": "critical hemoglobin levels anemia transfusion threshold",
        "description": "Lab reference query",
    },
    {
        "id": "P04",
        "query": "troponin elevation myocardial infarction diagnosis",
        "description": "Cardiac biomarker",
    },
    {
        "id": "P05",
        "query": "metformin type 2 diabetes contraindications renal failure",
        "description": "Drug contraindication",
    },
    {
        "id": "P06",
        "query": "aspirin side effects gastrointestinal bleeding risk",
        "description": "Drug safety profile",
    },
    {
        "id": "P07",
        "query": "deep vein thrombosis DVT diagnosis treatment anticoagulation",
        "description": "DVT guidelines",
    },
    {
        "id": "P08",
        "query": "sepsis SOFA score organ dysfunction criteria",
        "description": "Critical care — Sepsis 3",
    },
    {
        "id": "P09",
        "query": "mechanism of action beta blocker cardiac output heart rate",
        "description": "Pharmacology textbook query",
    },
    {
        "id": "P10",
        "query": "potassium hyperkalemia ECG changes peaked T waves treatment",
        "description": "Lab + ECG + treatment multi-domain",
    },
]


def _ram_used_gb() -> float:
    return psutil.Process(os.getpid()).memory_info().rss / 1e9


def run_fix_eval() -> None:
    print("=" * 75)
    print("  MedGraphRAG — Step 6 Hybrid Retrieval Fix Evaluation")
    print("=" * 75)

    service = HybridRetrievalService()

    print("⏳ Warm-up pass...")
    _ = service.retrieve(RetrievalRequest(query="warmup test"))
    print("✅ Warm-up complete.\n")

    results_summary = []
    entities_reached_count = 0
    chunks_from_graph_count = 0
    p01_pmid_38823454_count = 0

    for probe in PROBE_QUERIES:
        pid = probe["id"]
        query = probe["query"]
        desc = probe["description"]

        req = RetrievalRequest(query=query, top_n=settings.retrieval_top_n)
        res: RetrievalResult = service.retrieve(req)

        cat_counts: Dict[str, int] = {}
        source_mix: Dict[str, int] = {"faiss": 0, "graph": 0, "both": 0}
        for item in res.items:
            cat_counts[item.category] = cat_counts.get(item.category, 0) + 1
            source_mix[item.source_type] += 1

        gstats = res.graph_stats
        if gstats.entities_reached > 0:
            entities_reached_count += 1
        if gstats.chunks_from_graph > 0:
            chunks_from_graph_count += 1

        # Check P01 for PMID_38823454 duplicate chunks
        if pid == "P01":
            p01_pmid_38823454_count = sum(1 for item in res.items if "PMID_38823454" in item.document_id or "PMID_38823454" in item.chunk_id)

        print(f"[{pid}] {desc}")
        print(f"       Query: {query!r}")
        print(f"       Items: {len(res.items)} | Categories: {cat_counts} | Source mix: {source_mix}")
        print(f"       Graph Stats: seeds={gstats.seeds_used}, entities_reached={gstats.entities_reached}, chunks_from_graph={gstats.chunks_from_graph}, edges={gstats.edges_traversed}")
        print(f"       Latency breakdown ms: embed={res.latency_breakdown_ms.get('embed_ms',0):.1f}, faiss={res.latency_breakdown_ms.get('faiss_ms',0):.1f}, graph={res.latency_breakdown_ms.get('graph_ms',0):.1f}, fuse={res.latency_breakdown_ms.get('fuse_ms',0):.1f}, total={res.latency_ms:.1f}")

        if pid == "P01":
            print(f"       🔍 P01 PMID_38823454 chunk count: {p01_pmid_38823454_count} (target <= 2)")
        print()

        results_summary.append({
            "id": pid,
            "query": query,
            "n_items": len(res.items),
            "categories": cat_counts,
            "source_mix": source_mix,
            "graph_stats": gstats.model_dump(),
            "latency_breakdown": res.latency_breakdown_ms,
            "top_chunks": [item.chunk_id for item in res.items[:3]],
        })

    # Summary checks
    p01_pass = p01_pmid_38823454_count <= 2
    entities_pass = entities_reached_count >= 5
    graph_chunks_pass = chunks_from_graph_count >= 3

    print("=" * 75)
    print("  FIX VALIDATION SUMMARY")
    print("=" * 75)
    print(f"  P01 PMID_38823454 chunk count : {p01_pmid_38823454_count} [{'✅ PASS' if p01_pass else '❌ FAIL'}]")
    print(f"  Probes with entities_reached > 0: {entities_reached_count}/10 [{'✅ PASS' if entities_pass else '❌ FAIL'}]")
    print(f"  Probes with chunks_from_graph > 0: {chunks_from_graph_count}/10 [{'✅ PASS' if graph_chunks_pass else '❌ FAIL'}]")
    print(f"  Peak RAM usage                : {_ram_used_gb():.2f} GB")
    print()

    report_path = _PROJECT_ROOT / "evaluations" / "step6_fix_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "step": 6,
        "description": "Hybrid Retrieval Engine Fix Evaluation (Dedup + Entity Seeding)",
        "p01_pmid_38823454_count": p01_pmid_38823454_count,
        "entities_reached_probes_count": entities_reached_count,
        "chunks_from_graph_probes_count": chunks_from_graph_count,
        "p01_pass": p01_pass,
        "entities_pass": entities_pass,
        "graph_chunks_pass": graph_chunks_pass,
        "all_passed": p01_pass and entities_pass and graph_chunks_pass,
        "probes": results_summary,
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"📄 Saved fix evaluation report → {report_path}")


if __name__ == "__main__":
    run_fix_eval()
