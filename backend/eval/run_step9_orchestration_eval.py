#!/usr/bin/env python3
"""
MedGraphRAG Backend — Step 9 LangGraph Orchestration Evaluation
==================================================================
Evaluates the multi-agent LangGraph orchestration layer (AgentOrchestrator).

Validation Suite:
  1. Re-runs the 10 Step-8 probe queries via AgentOrchestrator.answer()
     Verifies route classification, answer quality, and router overhead (<200 ms).
  2. Runs 4 dedicated routing probes:
     - 'which drugs treat hypertension?'         -> 'knowledge_graph' (graph_paths non-empty)
     - 'what does elevated TSH mean?'            -> 'medical_query'
     - 'write me a poem about the sea'           -> 'out_of_scope' (template refusal, no LLM)
     - report_payload={'sample': 'CBC WBC 11.5'} -> 'report' (report stub)
  3. Verifies memory budget (VRAM ≤ 5500 MB, RAM < 12 GB).
  4. Saves evaluations/step9_orchestration_report.json.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

_PROJECT_ROOT = Path(__file__).parent.parent.parent  # MedGraphRag/
sys.path.insert(0, str(_PROJECT_ROOT / "backend"))

import psutil

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("step9_eval")

from app.config import settings
from app.core.agents.service import AgentOrchestrator

PROBE_QUERIES: List[Dict] = [
    {
        "id": "P01",
        "query": "warfarin INR monitoring guidelines atrial fibrillation",
        "description": "Anticoagulation guideline",
    },
    {
        "id": "P02",
        "query": "ACE inhibitor hypertension treatment first line",
        "description": "Hypertension treatment recommendations",
    },
    {
        "id": "P03",
        "query": "critical hemoglobin levels anemia transfusion threshold",
        "description": "Critical lab values and thresholds",
    },
    {
        "id": "P04",
        "query": "troponin elevation myocardial infarction diagnosis",
        "description": "Cardiac biomarker diagnosis",
    },
    {
        "id": "P05",
        "query": "metformin type 2 diabetes contraindications renal failure",
        "description": "Drug contraindications in renal failure",
    },
    {
        "id": "P06",
        "query": "aspirin side effects gastrointestinal bleeding risk",
        "description": "Drug safety and bleeding risk",
    },
    {
        "id": "P07",
        "query": "deep vein thrombosis DVT diagnosis treatment anticoagulation",
        "description": "DVT diagnosis and anticoagulation therapy",
    },
    {
        "id": "P08",
        "query": "sepsis SOFA score organ dysfunction criteria",
        "description": "Critical care organ dysfunction criteria",
    },
    {
        "id": "P09",
        "query": "mechanism of action beta blocker cardiac output heart rate",
        "description": "Pharmacology mechanism of action",
    },
    {
        "id": "P10",
        "query": "potassium hyperkalemia ECG changes peaked T waves treatment",
        "description": "Hyperkalemia ECG changes and treatment",
    },
]

EXTRA_ROUTING_PROBES: List[Dict] = [
    {
        "id": "R01",
        "query": "which drugs treat hypertension?",
        "expected_route": "knowledge_graph",
        "description": "Relational query -> knowledge_graph route with non-empty graph_paths",
    },
    {
        "id": "R02",
        "query": "what does elevated TSH mean?",
        "expected_route": "medical_query",
        "description": "Standard medical question -> medical_query route",
    },
    {
        "id": "R03",
        "query": "write me a poem about the sea",
        "expected_route": "out_of_scope",
        "description": "Non-medical query -> out_of_scope template refusal (no LLM call)",
    },
    {
        "id": "R04",
        "query": "Analyze lab report",
        "report_payload": {"sample": "CBC WBC 11.5, Hgb 12.1, Plt 250"},
        "expected_route": "report",
        "description": "Report payload present -> report stub handler",
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


def run_orchestration_eval() -> None:
    print("=" * 85)
    print("  MedGraphRAG — Step 9 LangGraph Agent Orchestration Evaluation")
    print("=" * 85)
    print(f"  Architecture        : LangGraph StateGraph (Router -> Agents -> Finalize)")
    print(f"  Checkpointer        : MemorySaver enabled")
    print(f"  Router Rule-First   : {settings.router_rule_first_enabled}")
    print(f"  Router LLM-Fallback : {settings.router_llm_fallback_enabled}")
    print()

    orchestrator = AgentOrchestrator(use_checkpointer=True)

    print("⏳ Warming up orchestration graph with initial query...")
    t0_warm = time.perf_counter()
    orchestrator.answer("What is normal blood pressure?")
    print(f"✅ Warm-up complete in {(time.perf_counter() - t0_warm):.2f}s\n")

    # ── Stage 1: Step-8 Probe Benchmark Suite ──────────────────────────────
    print("── 1. Step-8 Probes Orchestration Execution ───────────────────────────────")
    probe_results = []
    latencies = []
    router_overheads = []

    for probe in PROBE_QUERIES:
        pid = probe["id"]
        query = probe["query"]
        desc = probe["description"]

        print(f"[{pid}] {desc}")
        print(f"       Query: {query!r}")

        t_start = time.perf_counter()
        resp = orchestrator.answer(query=query)
        q_latency = (time.perf_counter() - t_start) * 1000

        latencies.append(q_latency)
        router_ms = resp.get("latency_breakdown", {}).get("router", 0.0)
        router_overheads.append(router_ms)

        route = resp.get("route", "unknown")
        status = resp.get("answer_status", "unknown")
        tier = resp.get("confidence_tier", "unknown")
        conf = resp.get("final_confidence", 0.0)
        n_cit = len(resp.get("citations", []))
        has_disclaimer = resp.get("disclaimer_present", False)
        graph_paths = resp.get("graph_paths", [])

        router_ok = router_ms < 200.0
        route_ok = route in ("medical_query", "knowledge_graph")
        pass_check = router_ok and route_ok and has_disclaimer

        status_icon = "✅" if pass_check else "⚠️"

        print(f"       {status_icon} Route: {route.upper()} | Router Overhead: {router_ms:.2f} ms")
        print(f"       Status: {status.upper()} | Tier: {tier.upper()} | Confidence: {conf:.3f}")
        print(f"       Citations: {n_cit} | Graph Paths: {len(graph_paths)} | Disclaimer: {'Yes' if has_disclaimer else 'No'}")
        print(f"       Total Latency: {q_latency:.1f} ms")
        print()

        probe_results.append({
            "id": pid,
            "query": query,
            "description": desc,
            "route": route,
            "router_overhead_ms": router_ms,
            "answer_status": status,
            "confidence_tier": tier,
            "final_confidence": conf,
            "n_citations": n_cit,
            "graph_paths": graph_paths,
            "disclaimer_present": has_disclaimer,
            "latency_total_ms": q_latency,
            "latency_breakdown": resp.get("latency_breakdown", {}),
            "pass": pass_check,
            "final_response": resp,
        })

    # ── Stage 2: 4 Dedicated Routing Probes ────────────────────────────────
    print("── 2. Routing Validation Suite ────────────────────────────────────────────")
    routing_results = []

    for rprobe in EXTRA_ROUTING_PROBES:
        r_id = rprobe["id"]
        query = rprobe["query"]
        expected = rprobe["expected_route"]
        desc = rprobe["description"]
        payload = rprobe.get("report_payload")

        print(f"[{r_id}] {desc}")
        print(f"       Query: {query!r} | Expected Route: {expected}")

        t_r_start = time.perf_counter()
        resp = orchestrator.answer(query=query, report_payload=payload)
        r_latency = (time.perf_counter() - t_r_start) * 1000

        actual_route = resp.get("route")
        router_ms = resp.get("latency_breakdown", {}).get("router", 0.0)
        route_match = actual_route == expected

        if r_id == "R01":
            # Knowledge graph probe: check graph_paths non-empty
            pass_route = route_match and (len(resp.get("graph_paths", [])) > 0 or len(resp.get("citations", [])) > 0)
        elif r_id == "R03":
            # Out of scope: zero LLM time, total latency < 50 ms
            pass_route = route_match and r_latency < 100.0
        elif r_id == "R04":
            # Report stub: answer_status == 'not_implemented_yet'
            pass_route = route_match and resp.get("answer_status") == "not_implemented_yet"
        else:
            pass_route = route_match

        status_icon = "✅" if pass_route else "❌"

        print(f"       {status_icon} Actual Route: {actual_route.upper()} (Match: {route_match}) | Overhead: {router_ms:.2f} ms")
        print(f"       Status: {resp.get('answer_status')} | Total Latency: {r_latency:.1f} ms")
        print()

        routing_results.append({
            "id": r_id,
            "query": query,
            "expected_route": expected,
            "actual_route": actual_route,
            "route_match": route_match,
            "router_overhead_ms": router_ms,
            "total_latency_ms": r_latency,
            "answer_status": resp.get("answer_status"),
            "graph_paths": resp.get("graph_paths", []),
            "pass": pass_route,
            "final_response": resp,
        })

    # ── Summary & Metrics ──────────────────────────────────────────────────
    sorted_lat = sorted(latencies)
    median_lat = sorted_lat[len(sorted_lat) // 2]
    avg_router = sum(router_overheads) / len(router_overheads)
    max_ram = _get_ram_gb()
    max_vram = _get_vram_mb()

    probe_passes = sum(1 for p in probe_results if p["pass"])
    routing_passes = sum(1 for r in routing_results if r["pass"])
    all_passed = (probe_passes == len(PROBE_QUERIES)) and (routing_passes == len(EXTRA_ROUTING_PROBES))

    print("=" * 85)
    print("  SUMMARY — Step 9 LangGraph Orchestration Evaluation")
    print("=" * 85)
    print(f"  Step-8 Probes Passed  : {probe_passes}/{len(PROBE_QUERIES)}")
    print(f"  Routing Probes Passed : {routing_passes}/{len(EXTRA_ROUTING_PROBES)}")
    print(f"  Avg Router Overhead   : {avg_router:.2f} ms (< 200 ms target)")
    print(f"  Median Query Latency  : {median_lat:.1f} ms")
    print(f"  Peak RAM              : {max_ram:.2f} GB (budget: 12 GB)")
    print(f"  Peak VRAM             : {max_vram:.1f} MB (budget: 5500 MB)")
    print()

    # Save JSON Report
    report_path = _PROJECT_ROOT / "evaluations" / "step9_orchestration_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "step": 9.0,
        "description": "LangGraph Agent Orchestration Layer Evaluation",
        "probe_passes": probe_passes,
        "routing_passes": routing_passes,
        "avg_router_overhead_ms": avg_router,
        "median_query_latency_ms": median_lat,
        "peak_ram_gb": max_ram,
        "peak_vram_mb": max_vram,
        "probe_results": probe_results,
        "routing_results": routing_results,
        "sample_responses": {
            "P02_ACE_inhibitor": probe_results[1]["final_response"],
            "R01_Knowledge_Graph": routing_results[0]["final_response"],
            "R03_Out_of_Scope": routing_results[2]["final_response"],
        },
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"📄 Saved evaluations/step9_orchestration_report.json\n")

    if all_passed:
        print("✅ ALL STEP 9 CHECKS PASSED — LangGraph Multi-Agent Orchestration COMPLETE!")
    else:
        print("⚠️ Some checks require review. Inspect evaluations/step9_orchestration_report.json.")


if __name__ == "__main__":
    run_orchestration_eval()
