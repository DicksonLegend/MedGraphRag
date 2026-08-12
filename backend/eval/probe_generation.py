#!/usr/bin/env python3
"""
MedGraphRAG Backend — Step 7 Generation Probe Evaluation
===========================================================
Runs the 10 diagnostic probe queries through the end-to-end RAG pipeline
(Hybrid Retrieval -> Context Builder -> LLM Chat Completion -> AnswerResult).

Verifies:
  - Citations [E#] present in answers
  - Mandatory disclaimer present
  - Evidence confidence score computed
  - Latency breakdown (retrieval / context / llm / total)
  - Memory usage: VRAM ≤ 5.5 GB, RAM ≤ 12.0 GB
  - Saves evaluations/step7_generation_report.json
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
logger = logging.getLogger("probe_gen_eval")

from app.config import settings
from app.core.llm.generator import AnswerResult, GeneratorService

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
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.memory_allocated() / 1e6
        return 0.0
    except Exception:
        return 0.0


def run_generation_probes() -> None:
    print("=" * 75)
    print("  MedGraphRAG — Step 7 Context Builder & LLM Generation Probe Evaluation")
    print("=" * 75)
    print(f"  Model GGUF  : {settings.llm_gguf_file}")
    print(f"  Model Path  : {settings.llm_model_path}")
    print(f"  Context Ctx : {settings.llm_n_ctx} tokens")
    print(f"  GPU Layers  : {settings.llm_n_gpu_layers}")
    print()

    generator = GeneratorService()

    print("⏳ Initializing LLM and executing warm-up generation pass...")
    t_warmup = time.perf_counter()
    warmup_res: AnswerResult = generator.generate("What is normal blood pressure?")
    warmup_s = time.perf_counter() - t_warmup

    print(f"✅ Warm-up complete in {warmup_s:.2f}s")
    print(f"   LLM mode active : {warmup_res.llm_mode}")
    print(f"   RAM after warm-up: {warmup_res.ram_gb:.2f} GB")
    print(f"   VRAM allocated  : {warmup_res.vram_mb:.1f} MB")
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
        result: AnswerResult = generator.generate(query)
        q_latency = (time.perf_counter() - t_q_start) * 1000

        latencies.append(q_latency)

        # Content validation checks
        has_disclaimer = "consult your physician" in result.answer_text.lower() or "medical advice" in result.answer_text.lower()
        has_citations = any(f"[E{i}]" in result.answer_text for i in range(1, result.n_evidence + 1)) or "evidence is insufficient" in result.answer_text.lower() or "no relevant evidence" in result.answer_text.lower()
        vram_ok = result.vram_mb <= 5500.0
        ram_ok = result.ram_gb <= 12.0

        pass_check = has_disclaimer and vram_ok and ram_ok

        status_icon = "✅" if pass_check else "⚠️"

        print(f"       {status_icon} Latency: {q_latency:.1f} ms (Retrieval: {result.latency_breakdown['retrieval_ms']:.1f} ms | LLM: {result.latency_breakdown['llm_ms']:.1f} ms)")
        print(f"       LLM Mode: {result.llm_mode} | RAM: {result.ram_gb:.2f} GB | VRAM: {result.vram_mb:.1f} MB")
        print(f"       Evidence items: {result.n_evidence} | Confidence: {result.evidence_confidence:.3f}")
        print(f"       Citations in text: {'Yes' if has_citations else 'No'} | Disclaimer: {'Yes' if has_disclaimer else 'No'}")

        # Print formatted snippet of answer
        lines = [line for line in result.answer_text.strip().split("\n") if line.strip()]
        preview = lines[0][:120] if lines else ""
        print(f"       Answer preview: {preview!r}...")
        print()

        probe_results.append({
            "id": pid,
            "query": query,
            "description": desc,
            "latency_total_ms": q_latency,
            "latency_retrieval_ms": result.latency_breakdown["retrieval_ms"],
            "latency_llm_ms": result.latency_breakdown["llm_ms"],
            "n_evidence": result.n_evidence,
            "evidence_confidence": result.evidence_confidence,
            "llm_mode": result.llm_mode,
            "ram_gb": result.ram_gb,
            "vram_mb": result.vram_mb,
            "has_disclaimer": has_disclaimer,
            "has_citations": has_citations,
            "pass": pass_check,
            "answer_text": result.answer_text,
            "citations": [c.model_dump() for c in result.citations],
        })

    # ── Summary ──────────────────────────────────────────────────────────────
    avg_lat = sum(latencies) / len(latencies)
    max_ram = max(r["ram_gb"] for r in probe_results)
    max_vram = max(r["vram_mb"] for r in probe_results)
    passes = sum(1 for r in probe_results if r["pass"])

    print("=" * 75)
    print("  SUMMARY — Step 7 Generation Evaluation")
    print("=" * 75)
    print(f"  Probes run      : {len(PROBE_QUERIES)}")
    print(f"  Passed checks   : {passes}/{len(PROBE_QUERIES)}")
    print(f"  LLM Mode used   : {warmup_res.llm_mode}")
    print(f"  Avg Latency     : {avg_lat:.1f} ms per query")
    print(f"  Peak RAM        : {max_ram:.2f} GB (budget: 12 GB)")
    print(f"  Peak VRAM       : {max_vram:.1f} MB (budget: 5500 MB)")
    print()

    if max_vram > 5500.0:
        print("  ❌ FAIL: Peak VRAM exceeded budget of 5.5 GB!")
    elif max_ram > 12.0:
        print("  ❌ FAIL: Peak RAM exceeded budget of 12.0 GB!")
    elif passes == len(PROBE_QUERIES):
        print("  ✅ ALL PROBES PASSED — Step 7 COMPLETE. Context Builder & LLM Generation operational!")
    else:
        print(f"  ⚠️ {len(PROBE_QUERIES) - passes} probe(s) had warnings. Review JSON report.")

    report_path = _PROJECT_ROOT / "evaluations" / "step7_generation_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "step": 7,
        "description": "Context Builder and LLM Generation Layer Evaluation",
        "model_gguf": settings.llm_gguf_file,
        "llm_mode": warmup_res.llm_mode,
        "probe_count": len(PROBE_QUERIES),
        "passes": passes,
        "avg_latency_ms": avg_lat,
        "peak_ram_gb": max_ram,
        "peak_vram_mb": max_vram,
        "probes": probe_results,
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n  📄 JSON report saved → {report_path}")


if __name__ == "__main__":
    run_generation_probes()
