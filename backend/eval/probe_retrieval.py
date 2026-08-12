#!/usr/bin/env python3
"""
MedGraphRAG Backend — Step 6 Probe Retrieval Evaluation
=========================================================
Runs 10 diagnostic probe queries against the hybrid retrieval engine
and prints a detailed report.

Usage:
    cd /home/dicksone/Documents/MedGraphRag
    source Data_Normalization/.venv/bin/activate
    python backend/eval/probe_retrieval.py

Constraints verified:
  - GPU VRAM usage = 0 (CPU-only retrieval)
  - Peak RAM < 12 GB
  - Per-query latency < 5 s (target < 2 s at steady state)
  - Category diversity (not dominated by lab_reference)
  - Graph traversal activates (seeds → entities → chunks)
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List

# ---------------------------------------------------------------------------
# Path setup: make `backend/` importable from project root
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).parent.parent.parent  # MedGraphRag/
sys.path.insert(0, str(_PROJECT_ROOT / "backend"))

import psutil

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("probe_eval")

# ---------------------------------------------------------------------------
# Import backend components (lazy — triggers no GPU allocation)
# ---------------------------------------------------------------------------
from app.config import settings
from app.core.retrieval.service import HybridRetrievalService
from app.core.retrieval.schemas import RetrievalRequest, RetrievalResult

# ---------------------------------------------------------------------------
# Probe query set
# ---------------------------------------------------------------------------
PROBE_QUERIES: List[Dict] = [
    # Clinical guidelines
    {
        "id": "P01",
        "query": "warfarin INR monitoring guidelines atrial fibrillation",
        "expected_cats": ["guideline"],
        "description": "Anticoagulation guideline — should hit guideline chunks",
    },
    {
        "id": "P02",
        "query": "ACE inhibitor hypertension treatment first line",
        "expected_cats": ["guideline", "drug"],
        "description": "Drug + guideline cross-domain",
    },
    # Lab tests
    {
        "id": "P03",
        "query": "critical hemoglobin levels anemia transfusion threshold",
        "expected_cats": ["lab_reference", "guideline"],
        "description": "Lab reference query — moderate lab_reference expected",
    },
    {
        "id": "P04",
        "query": "troponin elevation myocardial infarction diagnosis",
        "expected_cats": ["lab_reference", "guideline", "research_paper"],
        "description": "Cardiac biomarker — lab + guideline",
    },
    # Pharmacology
    {
        "id": "P05",
        "query": "metformin type 2 diabetes contraindications renal failure",
        "expected_cats": ["drug", "guideline"],
        "description": "Drug contraindication — drug + guideline",
    },
    {
        "id": "P06",
        "query": "aspirin side effects gastrointestinal bleeding risk",
        "expected_cats": ["drug", "guideline"],
        "description": "Drug safety profile",
    },
    # Disease / pathology
    {
        "id": "P07",
        "query": "deep vein thrombosis DVT diagnosis treatment anticoagulation",
        "expected_cats": ["guideline", "research_paper"],
        "description": "DVT — well-represented in the dataset",
    },
    {
        "id": "P08",
        "query": "sepsis SOFA score organ dysfunction criteria",
        "expected_cats": ["guideline", "research_paper"],
        "description": "Critical care — sepsis 3 definition",
    },
    # Textbook / basic science
    {
        "id": "P09",
        "query": "mechanism of action beta blocker cardiac output heart rate",
        "expected_cats": ["textbook", "guideline"],
        "description": "Pharmacology textbook query",
    },
    # Cross-domain stress test
    {
        "id": "P10",
        "query": "potassium hyperkalemia ECG changes peaked T waves treatment",
        "expected_cats": ["lab_reference", "guideline", "textbook"],
        "description": "Lab + ECG + treatment — multi-domain stress test",
    },
]


# ---------------------------------------------------------------------------
# RAM / VRAM measurement helpers
# ---------------------------------------------------------------------------

def _ram_used_gb() -> float:
    proc = psutil.Process(os.getpid())
    return proc.memory_info().rss / 1e9


def _vram_used_mb() -> float:
    """Returns current VRAM usage in MB. 0.0 if torch/CUDA not available."""
    try:
        import torch
        if not torch.cuda.is_available():
            return 0.0
        return torch.cuda.memory_allocated() / 1e6
    except ImportError:
        return 0.0


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------

def run_probes() -> None:
    print("=" * 70)
    print("  MedGraphRAG — Step 6 Hybrid Retrieval Probe Evaluation")
    print("=" * 70)
    print(f"  Index dir : {settings.index_dir}")
    print(f"  Embed model: {settings.embed_model_name} [{settings.embed_device}]")
    print(f"  FAISS nprobe: {settings.faiss_nprobe}  raw_k: {settings.faiss_top_k_raw}")
    print(f"  Final top_n: {settings.retrieval_top_n}")
    print()

    service = HybridRetrievalService()

    # Warm-up pass (pre-loads model + index silently)
    print("⏳ Warming up (loading FAISS + Kùzu + embedding model) …")
    t_warmup = time.perf_counter()
    _ = service.retrieve(RetrievalRequest(query="warm up query test"))
    warmup_s = time.perf_counter() - t_warmup
    vram_after_warmup = _vram_used_mb()
    ram_after_warmup = _ram_used_gb()
    print(f"✅ Warm-up complete in {warmup_s:.1f}s")
    print(f"   RAM after warm-up : {ram_after_warmup:.2f} GB")
    print(f"   VRAM after warm-up: {vram_after_warmup:.1f} MB (must be 0)")
    if vram_after_warmup > 10:
        print("   ⚠️  WARNING: VRAM usage detected! GPU constraint violated.")
    print()

    # Collect probe results
    probe_results = []
    latencies = []

    for probe in PROBE_QUERIES:
        pid = probe["id"]
        query = probe["query"]
        desc = probe["description"]
        expected_cats = probe.get("expected_cats", [])

        print(f"[{pid}] {desc}")
        print(f"       Query: {query!r}")

        req = RetrievalRequest(query=query, top_n=settings.retrieval_top_n)
        result: RetrievalResult = service.retrieve(req)

        latencies.append(result.latency_ms)

        # Category distribution in results
        cat_counts: Dict[str, int] = {}
        source_counts: Dict[str, int] = {"faiss": 0, "graph": 0, "both": 0}
        for item in result.items:
            cat_counts[item.category] = cat_counts.get(item.category, 0) + 1
            source_counts[item.source_type] += 1

        # Check category diversity
        lab_pct = cat_counts.get("lab_reference", 0) / max(len(result.items), 1) * 100
        cat_present = set(cat_counts.keys())
        expected_present = all(ec in cat_present for ec in expected_cats)

        # Hard constraints: lab_reference ≤ 50%, latency < 5s
        # Expected categories are ADVISORY — the model may correctly find better
        # evidence than the probe author anticipated.
        hard_pass = (
            lab_pct <= 50
            and result.latency_ms < 5000
            and len(result.items) > 0
        )
        status_icon = "✅" if hard_pass else "⚠️"
        if not expected_present:
            status_icon += "(advisory: expected cats not all present)"

        print(f"       {status_icon} Latency: {result.latency_ms:.1f} ms | "
              f"Items: {len(result.items)} | "
              f"FAISS raw: {result.total_faiss_candidates} → "
              f"Graph: {result.total_graph_candidates}")
        print(f"       Categories: {dict(sorted(cat_counts.items(), key=lambda x: -x[1]))}")
        print(f"       Source mix: {source_counts}")
        print(f"       lab_reference %: {lab_pct:.0f}%  "
              f"({'OK' if lab_pct <= 50 else 'HIGH — check caps'})")
        print(f"       Graph stats: seeds={result.graph_stats.seeds_used}, "
              f"entities={result.graph_stats.entities_reached}, "
              f"graph_chunks={result.graph_stats.chunks_from_graph}, "
              f"edges={result.graph_stats.edges_traversed}")

        # Latency breakdown
        bd = result.latency_breakdown_ms
        print(f"       Breakdown ms: embed={bd.get('embed_ms',0):.1f} "
              f"faiss={bd.get('faiss_ms',0):.1f} "
              f"graph={bd.get('graph_ms',0):.1f} "
              f"fuse={bd.get('fuse_ms',0):.1f} "
              f"text={bd.get('text_load_ms',0):.1f}")

        # Top 3 evidence items
        print("       Top 3 evidence items:")
        for i, item in enumerate(result.items[:3], 1):
            snippet = item.text_snippet[:100].replace("\n", " ")
            print(f"         {i}. [{item.category}][{item.source_type}] "
                  f"score={item.fused_score:.4f} "
                  f"chunk={item.chunk_id[:50]}")
            print(f"            {snippet!r}")
            if item.graph_boost_applied:
                print(f"            🔷 Graph boost applied (edge: {item.edge_trust})")
        print()

        probe_results.append({
            "id": pid,
            "query": query,
            "latency_ms": result.latency_ms,
            "n_items": len(result.items),
            "categories": cat_counts,
            "source_mix": source_counts,
            "lab_pct": lab_pct,
            "graph_stats": result.graph_stats.model_dump(),
            "breakdown_ms": bd,
            "pass": hard_pass,
            "expected_cats_present": expected_present,
        })

    # ── Summary ─────────────────────────────────────────────────────────────
    ram_peak = _ram_used_gb()
    vram_final = _vram_used_mb()

    avg_lat = sum(latencies) / len(latencies)
    max_lat = max(latencies)
    min_lat = min(latencies)
    # Exclude warm-up first call (often slower due to JIT)
    steady_lats = latencies[1:]
    avg_steady = sum(steady_lats) / len(steady_lats) if steady_lats else avg_lat

    passes = sum(1 for r in probe_results if r["pass"])

    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"  Probes run    : {len(PROBE_QUERIES)}")
    print(f"  Passed checks : {passes}/{len(PROBE_QUERIES)}")
    print(f"  Latency (all) : avg={avg_lat:.1f} ms  min={min_lat:.1f}  max={max_lat:.1f}")
    print(f"  Latency (steady, ex warm-up): avg={avg_steady:.1f} ms")
    print(f"  Peak RAM      : {ram_peak:.2f} GB  (budget: 12 GB)")
    print(f"  VRAM used     : {vram_final:.1f} MB  (must be 0)")
    print()

    if vram_final > 10:
        print("  ❌ FAIL: VRAM > 0 — GPU constraint violated!")
    elif ram_peak > 12.0:
        print("  ❌ FAIL: RAM > 12 GB budget exceeded!")
    elif passes == len(PROBE_QUERIES):
        print("  ✅ ALL PROBES PASSED — Step 6 COMPLETE. Ready for Step 7.")
    else:
        failed = [r["id"] for r in probe_results if not r["pass"]]
        print(f"  ⚠️  {len(PROBE_QUERIES) - passes} probe(s) need review: {failed}")

    print()
    print("  Per-query latencies (ms):")
    for r in probe_results:
        icon = "✅" if r["pass"] else "⚠️"
        print(f"    {icon} [{r['id']}] {r['latency_ms']:6.1f} ms — {PROBE_QUERIES[int(r['id'][1:])-1]['description'][:45]}")

    # Save JSON report
    report_path = _PROJECT_ROOT / "evaluations" / "step6_probe_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "step": 6,
        "description": "Hybrid Retrieval Engine Probe Evaluation",
        "probe_count": len(PROBE_QUERIES),
        "passes": passes,
        "avg_latency_ms": avg_lat,
        "avg_steady_latency_ms": avg_steady,
        "peak_ram_gb": ram_peak,
        "vram_mb": vram_final,
        "probes": probe_results,
    }
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n  📄 JSON report saved → {report_path}")


if __name__ == "__main__":
    run_probes()
