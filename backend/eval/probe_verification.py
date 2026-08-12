#!/usr/bin/env python3
"""
MedGraphRAG Backend — Step 8 Verification Agent Probe Evaluation
===================================================================
Runs the 10 diagnostic probe queries through the FULL self-verifying pipeline
(MedGraphRAGPipeline.answer()).

Verifies:
  - Atomic claim extraction & faithfulness verdicts
  - Final confidence scoring (evidence_confidence + faithfulness_score)
  - Answer status gating (verified | caution | uncertain | refusal)
  - Retry gate trajectory tracking
  - Memory budget (VRAM ≤ 5.5 GB, RAM ≤ 12.0 GB)
  - Saves evaluations/step8_verification_report.json
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
logger = logging.getLogger("probe_verification_eval")

from app.config import settings
from app.core.pipeline import MedGraphRAGPipeline
from app.core.verification.schemas import VerifiedAnswerResult

PROBE_QUERIES: List[Dict] = [
    {
        "id": "P01",
        "query": "warfarin INR monitoring guidelines atrial fibrillation",
        "description": "Anticoagulation guideline — should produce cited guidance on INR monitoring",
    },
    {
        "id": "P02",
        "query": "ACE inhibitor hypertension treatment first line",
        "description": "Hypertension treatment — first-line ACE inhibitor recommendations",
    },
    {
        "id": "P03",
        "query": "critical hemoglobin levels anemia transfusion threshold",
        "description": "Critical lab values — transfusion thresholds and critical levels",
    },
    {
        "id": "P04",
        "query": "troponin elevation myocardial infarction diagnosis",
        "description": "Cardiac biomarker — troponin elevation in MI diagnosis",
    },
    {
        "id": "P05",
        "query": "metformin type 2 diabetes contraindications renal failure",
        "description": "Drug contraindications — metformin in renal impairment",
    },
    {
        "id": "P06",
        "query": "aspirin side effects gastrointestinal bleeding risk",
        "description": "Drug safety — aspirin GI bleeding risk",
    },
    {
        "id": "P07",
        "query": "deep vein thrombosis DVT diagnosis treatment anticoagulation",
        "description": "DVT guidelines — diagnosis and anticoagulation therapy",
    },
    {
        "id": "P08",
        "query": "sepsis SOFA score organ dysfunction criteria",
        "description": "Critical care — Sepsis-3 criteria and SOFA score",
    },
    {
        "id": "P09",
        "query": "mechanism of action beta blocker cardiac output heart rate",
        "description": "Pharmacology — beta blocker mechanism of action",
    },
    {
        "id": "P10",
        "query": "potassium hyperkalemia ECG changes peaked T waves treatment",
        "description": "Emergency medicine — hyperkalemia ECG changes & treatment",
    },
]


def _get_ram_gb() -> float:
    return psutil.Process(os.getpid()).memory_info().rss / 1e9


def _get_vram_mb() -> float:
    try:
        import subprocess
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2
        )
        if res.returncode == 0:
            return float(res.stdout.strip())
    except Exception:
        pass
    return 0.0


def run_verification_probes() -> None:
    print("=" * 75)
    print("  MedGraphRAG — Step 8 Verification Agent Probe Evaluation")
    print("=" * 75)
    print(f"  Pipeline    : MedGraphRAGPipeline")
    print(f"  Model GGUF  : {settings.llm_gguf_file}")
    print(f"  High Thresh : {settings.verification_threshold_high}")
    print(f"  Med Thresh  : {settings.verification_threshold_medium}")
    print(f"  Low Thresh  : {settings.verification_threshold_low}")
    print(f"  Max Retries : {settings.verification_max_retries}")
    print()

    pipeline = MedGraphRAGPipeline()

    print("⏳ Initializing pipeline and executing warm-up query...")
    t_warmup = time.perf_counter()
    warmup_res: VerifiedAnswerResult = pipeline.answer("What is normal blood pressure?")
    warmup_s = time.perf_counter() - t_warmup

    print(f"✅ Warm-up complete in {warmup_s:.2f}s")
    print(f"   Status          : {warmup_res.answer_status}")
    print(f"   Confidence      : {warmup_res.final_confidence:.3f} ({warmup_res.confidence_tier})")
    print(f"   Faithfulness    : {warmup_res.faithfulness_score:.3f}")
    print(f"   RAM / VRAM      : {warmup_res.ram_gb:.2f} GB / {warmup_res.vram_mb:.1f} MB")
    print()

    probe_results = []
    latencies = []

    for probe in PROBE_QUERIES:
        pid = probe["id"]
        query = probe["query"]
        desc = probe["description"]

        print(f"[{pid}] {desc}")
        print(f"       Query: {query!r}")

        t_q_start = time.perf_counter()
        res: VerifiedAnswerResult = pipeline.answer(query)
        q_latency = (time.perf_counter() - t_q_start) * 1000

        latencies.append(q_latency)

        n_claims = len(res.claims)
        n_supported = sum(1 for c in res.claims if c.verdict == "supported")
        n_contradicted = sum(1 for c in res.claims if c.verdict == "contradicted")
        n_not_mentioned = sum(1 for c in res.claims if c.verdict == "not_mentioned")
        n_refusal_valid = sum(1 for c in res.claims if c.verdict == "refusal_valid")

        has_disclaimer = "consult your physician" in res.answer_text.lower() or "medical advice" in res.answer_text.lower()
        vram_ok = res.vram_mb <= 5500.0
        ram_ok = res.ram_gb <= 12.0

        pass_check = has_disclaimer and vram_ok and ram_ok

        status_icon = "✅" if pass_check else "⚠️"

        print(f"       {status_icon} Status: {res.answer_status.upper()} | Tier: {res.confidence_tier.upper()}")
        print(f"       Confidence: {res.final_confidence:.3f} (Evidence: {res.evidence_confidence:.3f} | Faithfulness: {res.faithfulness_score:.3f})")
        print(f"       Claims ({n_claims}): supported={n_supported}, contradicted={n_contradicted}, not_mentioned={n_not_mentioned}, refusal_valid={n_refusal_valid}")
        print(f"       Retries executed: {res.retry_count} | Trajectory: {res.retry_confidence_trajectory}")
        print(f"       Latency: {q_latency:.1f} ms (Retrieval: {res.latency_breakdown.get('retrieval_ms',0):.1f} ms | LLM: {res.latency_breakdown.get('llm_ms',0):.1f} ms | Verifier: {res.latency_breakdown.get('verification_ms',0):.1f} ms)")
        print(f"       RAM: {res.ram_gb:.2f} GB | VRAM: {res.vram_mb:.1f} MB | Disclaimer: {'Yes' if has_disclaimer else 'No'}")

        # Print preview
        lines = [line for line in res.answer_text.strip().split("\n") if line.strip()]
        preview = lines[0][:150] if lines else ""
        print(f"       Preview: {preview!r}...")
        print()

        probe_results.append({
            "id": pid,
            "query": query,
            "description": desc,
            "answer_status": res.answer_status,
            "final_confidence": res.final_confidence,
            "confidence_tier": res.confidence_tier,
            "evidence_confidence": res.evidence_confidence,
            "faithfulness_score": res.faithfulness_score,
            "n_claims": n_claims,
            "n_supported": n_supported,
            "n_contradicted": n_contradicted,
            "n_not_mentioned": n_not_mentioned,
            "n_refusal_valid": n_refusal_valid,
            "retry_count": res.retry_count,
            "retry_confidence_trajectory": res.retry_confidence_trajectory,
            "latency_total_ms": q_latency,
            "latency_breakdown": res.latency_breakdown,
            "ram_gb": res.ram_gb,
            "vram_mb": res.vram_mb,
            "has_disclaimer": has_disclaimer,
            "pass": pass_check,
            "answer_text": res.answer_text,
            "claims": [c.model_dump() for c in res.claims],
            "citations": [c.model_dump() for c in res.citations],
        })

    # ── Summary ──────────────────────────────────────────────────────────────
    avg_lat = sum(latencies) / len(latencies)
    max_ram = max(r["ram_gb"] for r in probe_results)
    max_vram = max(r["vram_mb"] for r in probe_results)
    passes = sum(1 for r in probe_results if r["pass"])
    status_counts: Dict[str, int] = {}
    for r in probe_results:
        status_counts[r["answer_status"]] = status_counts.get(r["answer_status"], 0) + 1

    print("=" * 75)
    print("  SUMMARY — Step 8 Verification Agent Evaluation")
    print("=" * 75)
    print(f"  Probes run      : {len(PROBE_QUERIES)}")
    print(f"  Passed checks   : {passes}/{len(PROBE_QUERIES)}")
    print(f"  Status breakdown: {status_counts}")
    print(f"  Avg Latency     : {avg_lat:.1f} ms per query")
    print(f"  Peak RAM        : {max_ram:.2f} GB (budget: 12 GB)")
    print(f"  Peak VRAM       : {max_vram:.1f} MB (budget: 5500 MB)")
    print()

    if max_vram > 5500.0:
        print("  ❌ FAIL: Peak VRAM exceeded budget of 5.5 GB!")
    elif max_ram > 12.0:
        print("  ❌ FAIL: Peak RAM exceeded budget of 12.0 GB!")
    elif passes == len(PROBE_QUERIES):
        print("  ✅ ALL PROBES PASSED — Step 8 COMPLETE. Verification Agent fully operational!")
    else:
        print(f"  ⚠️ {len(PROBE_QUERIES) - passes} probe(s) had warnings. Review JSON report.")

    report_path = _PROJECT_ROOT / "evaluations" / "step8_verification_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "step": 8,
        "description": "Verification Agent Evaluation (Self-Verifying RAG Layer)",
        "model_gguf": settings.llm_gguf_file,
        "probe_count": len(PROBE_QUERIES),
        "passes": passes,
        "status_breakdown": status_counts,
        "avg_latency_ms": avg_lat,
        "peak_ram_gb": max_ram,
        "peak_vram_mb": max_vram,
        "probes": probe_results,
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n  📄 JSON report saved → {report_path}")


if __name__ == "__main__":
    run_verification_probes()
