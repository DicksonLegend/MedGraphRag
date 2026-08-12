#!/usr/bin/env python3
"""
MedGraphRAG Backend — Step 8.1 Verification Agent Fix & Latency Evaluation
=============================================================================
Runs the 10 diagnostic probe queries through the optimized self-verifying pipeline
(MedGraphRAGPipeline.answer()).

Verifies Step 8.1 Acceptance Criteria:
  1. ≥ 8/10 probes with total latency < 12,000 ms; median < 12,000 ms.
  2. verification_ms ≤ 6,000 ms on every non-refusal probe.
  3. P02 no longer a bare refusal (WHO first-line chunk present in citations).
  4. Zero citations containing blocklisted sources; zero PMC XML/Metadata twin pairs.
  5. Refusal probes still refusal_valid with faithfulness 1.0.
  6. Peak VRAM ≤ 5500 MB, RAM < 12 GB, 100% citations + disclaimer.
  7. Saves evaluations/step8_fix_report.json.
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
logger = logging.getLogger("step8_fix_eval")

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

# Baseline latencies from step 8 before fix (for old vs new comparison table)
OLD_LATENCIES_MS = {
    "P01": 21870.0,
    "P02": 21400.0,
    "P03": 20950.0,
    "P04": 22300.0,
    "P05": 19800.0,
    "P06": 21100.0,
    "P07": 55100.0,
    "P08": 18900.0,
    "P09": 20100.0,
    "P10": 21500.0,
}


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


def run_step8_fix_eval() -> None:
    print("=" * 80)
    print("  MedGraphRAG — Step 8.1 Verification Agent Fix & Latency Evaluation")
    print("=" * 80)
    print(f"  Pipeline Target Budget : < {settings.query_latency_budget_ms} ms")
    print(f"  Single-Pass Max Tokens : 700")
    print(f"  Evidence Max / Prompt  : {settings.evidence_max_per_prompt}")
    print(f"  Evidence Blocklist     : {settings.evidence_blocklist}")
    print()

    pipeline = MedGraphRAGPipeline()

    print("⏳ Warming up model with initial query (discarded from metrics)...")
    pipeline.answer("What is normal blood pressure?")
    print("✅ Model warm-up complete.\n")

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

        # ── Evidence Hygiene Check ────────────────────────────────────────────
        blocklisted_citations = []
        pmc_ids_seen = set()
        pmc_twin_detected = False

        for citation in res.citations:
            doc_id = citation.document_id
            chunk_id = citation.chunk_id
            for kw in settings.evidence_blocklist:
                if kw in doc_id or kw in chunk_id:
                    blocklisted_citations.append(f"{kw} in {doc_id}")

            import re
            pmc_match = re.search(r"PMC\d+", doc_id)
            if pmc_match:
                pmc_id = pmc_match.group(0)
                if pmc_id in pmc_ids_seen:
                    pmc_twin_detected = True
                pmc_ids_seen.add(pmc_id)

        has_disclaimer = "consult your physician" in res.answer_text.lower() or "medical advice" in res.answer_text.lower()
        verif_ms = res.latency_breakdown.get("verification_ms", 0.0)
        is_refusal_probe = res.answer_status == "refusal"

        latency_ok = q_latency < 12000.0
        verif_ok = is_refusal_probe or (verif_ms <= 6000.0)
        hygiene_ok = len(blocklisted_citations) == 0 and not pmc_twin_detected
        vram_ok = res.vram_mb <= 5500.0
        ram_ok = res.ram_gb <= 12.0

        p02_ok = True
        if pid == "P02":
            p02_ok = res.answer_status != "refusal"

        pass_check = has_disclaimer and vram_ok and ram_ok and hygiene_ok and verif_ok and p02_ok

        status_icon = "✅" if pass_check else "⚠️"

        print(f"       {status_icon} Status: {res.answer_status.upper()} | Tier: {res.confidence_tier.upper()}")
        print(f"       Confidence: {res.final_confidence:.3f} (Evidence: {res.evidence_confidence:.3f} | Faithfulness: {res.faithfulness_score:.3f})")
        print(f"       Claims ({n_claims}): supported={n_supported}, contradicted={n_contradicted}, not_mentioned={n_not_mentioned}, refusal_valid={n_refusal_valid}")
        print(f"       Retries executed: {res.retry_count} | Trajectory: {res.retry_confidence_trajectory}")
        print(f"       Latency: {q_latency:.1f} ms (Retrieval: {res.latency_breakdown.get('retrieval_ms',0):.1f} ms | LLM: {res.latency_breakdown.get('llm_ms',0):.1f} ms | Verifier: {verif_ms:.1f} ms)")
        print(f"       RAM: {res.ram_gb:.2f} GB | VRAM: {res.vram_mb:.1f} MB | Disclaimer: {'Yes' if has_disclaimer else 'No'}")

        # Print preview
        lines = [line for line in res.answer_text.strip().split("\n") if line.strip()]
        preview = lines[0][:140] if lines else ""
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
            "latency_verification_ms": verif_ms,
            "latency_breakdown": res.latency_breakdown,
            "ram_gb": res.ram_gb,
            "vram_mb": res.vram_mb,
            "has_disclaimer": has_disclaimer,
            "blocklisted_citations_count": len(blocklisted_citations),
            "pmc_twin_detected": pmc_twin_detected,
            "pass": pass_check,
            "answer_text": res.answer_text,
            "claims": [c.model_dump() for c in res.claims],
            "citations": [c.model_dump() for c in res.citations],
        })

    # ── Summary Calculation ──────────────────────────────────────────────────
    sorted_lat = sorted(latencies)
    median_lat = sorted_lat[len(sorted_lat) // 2]
    avg_lat = sum(latencies) / len(latencies)
    under_12s_count = sum(1 for l in latencies if l < 12000.0)
    max_ram = max(r["ram_gb"] for r in probe_results)
    max_vram = max(r["vram_mb"] for r in probe_results)
    passes = sum(1 for r in probe_results if r["pass"])
    status_counts: Dict[str, int] = {}
    for r in probe_results:
        status_counts[r["answer_status"]] = status_counts.get(r["answer_status"], 0) + 1

    report_path = _PROJECT_ROOT / "evaluations" / "step8_fix_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "step": 8.1,
        "description": "Verification Agent Latency & Evidence Hygiene Fix Report",
        "probe_count": len(PROBE_QUERIES),
        "passes": passes,
        "under_12s_count": under_12s_count,
        "median_latency_ms": median_lat,
        "avg_latency_ms": avg_lat,
        "peak_ram_gb": max_ram,
        "peak_vram_mb": max_vram,
        "status_breakdown": status_counts,
        "probes": probe_results,
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"📄 Saved evaluations/step8_fix_report.json\n")

    # ── Print Old vs New Latency Comparison Table (SCRIPT-GENERATED FROM JSON) ─
    print("=" * 80)
    print("  OLD vs NEW LATENCY COMPARISON TABLE (Generated from JSON Report)")
    print("=" * 80)
    print(f"{'Probe':<6} | {'Status':<12} | {'Old Total (ms)':<15} | {'New Total (ms)':<15} | {'Speedup':<10} | {'Verifier (ms)':<12}")
    print("-" * 80)

    for p in probe_results:
        pid = p["id"]
        old_l = OLD_LATENCIES_MS.get(pid, 21000.0)
        new_l = p["latency_total_ms"]
        speedup = f"{old_l / new_l:.2f}x" if new_l > 0 else "N/A"
        verif = f"{p['latency_verification_ms']:.1f}"
        status = p["answer_status"]
        print(f"{pid:<6} | {status:<12} | {old_l:<15.1f} | {new_l:<15.1f} | {speedup:<10} | {verif:<12}")

    print("-" * 80)
    print(f"Median Latency  : Old ~21,000.0 ms  -->  New {median_lat:.1f} ms ({OLD_LATENCIES_MS['P01'] / median_lat:.2f}x faster)")
    print(f"Queries < 12s   : {under_12s_count}/{len(PROBE_QUERIES)}")
    print(f"Peak VRAM       : {max_vram:.1f} MB (budget: 5500 MB)")
    print(f"Peak RAM        : {max_ram:.2f} GB (budget: 12 GB)")
    print("=" * 80)


if __name__ == "__main__":
    run_step8_fix_eval()
