#!/usr/bin/env python3
"""
MedGraphRAG — Step 19: Guardrails & Knowledge-Gap Evaluation Runner
===================================================================
Executes test suites for:
  - F1: Cross-Modal Discrepancy Guardrail
  - F2: Epistemic Knowledge-Gap Mapper
Generates evaluations/step19_guardrails_eval_report.json with full test output,
payloads, assertions, latency benchmarks, and verification statuses.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("guardrails_eval")

from app.core.guardrail.discrepancy import detect_discrepancies
from app.core.guardrail.knowledge_gaps import map_knowledge_gaps
from app.core.guardrail.schemas import DiscrepancyAlert, KnowledgeGap


def run_discrepancy_tests() -> Dict[str, Any]:
    logger.info("--- Running F1: Cross-Modal Discrepancy Guardrail Test Suite ---")
    results = []

    # Case 1: Visual positive (0.88) vs text negation (pneumothorax) -> HIGH severity alert
    t0 = time.perf_counter()
    vf_1 = [{"label": "pneumothorax", "score": 0.88, "negated": False, "neg_score": 0.12}]
    te_1 = [{"snippet": "Chest radiograph demonstrates clear lungs with no pneumothorax or effusion.", "source_id": "doc_rad_001", "category": "radiology"}]
    alerts_1 = detect_discrepancies(vf_1, te_1)
    lat_1 = (time.perf_counter() - t0) * 1000

    assert len(alerts_1) == 1, f"Expected 1 alert, got {len(alerts_1)}"
    assert alerts_1[0].finding == "pneumothorax"
    assert alerts_1[0].severity == "HIGH"
    assert alerts_1[0].visual_evidence.score == 0.88
    assert alerts_1[0].visual_evidence.negated is False
    assert "manual radiologist review" in alerts_1[0].recommendation.lower()

    results.append({
        "test_name": "test_visual_positive_vs_text_negation_pneumothorax",
        "description": "Rule A: Visual positive (0.88) vs. text negation -> HIGH severity alert",
        "status": "PASSED",
        "latency_ms": round(lat_1, 3),
        "inputs": {"visual_findings": vf_1, "text_evidence": te_1},
        "output_alerts": [a.model_dump() for a in alerts_1],
    })
    logger.info("  ✅ Case 1 Passed: Visual positive vs text negation (Pneumothorax -> HIGH alert)")

    # Case 2: Visual negated (0.85) vs text positive assertion (effusion) -> HIGH severity alert
    t0 = time.perf_counter()
    vf_2 = [{"label": "pleural_effusion", "score": 0.15, "negated": True, "neg_score": 0.85}]
    te_2 = [{"snippet": "There is moderate bilateral pleural effusion with blunting of the costophrenic angles.", "source_id": "doc_rad_002", "category": "radiology"}]
    alerts_2 = detect_discrepancies(vf_2, te_2)
    lat_2 = (time.perf_counter() - t0) * 1000

    assert len(alerts_2) == 1, f"Expected 1 alert, got {len(alerts_2)}"
    assert alerts_2[0].finding == "pleural_effusion"
    assert alerts_2[0].severity == "HIGH"
    assert alerts_2[0].visual_evidence.negated is True

    results.append({
        "test_name": "test_visual_negated_vs_text_positive_effusion",
        "description": "Rule B: Visual negated (0.85) vs. text positive assertion -> HIGH severity alert",
        "status": "PASSED",
        "latency_ms": round(lat_2, 3),
        "inputs": {"visual_findings": vf_2, "text_evidence": te_2},
        "output_alerts": [a.model_dump() for a in alerts_2],
    })
    logger.info("  ✅ Case 2 Passed: Visual negated vs text positive (Pleural effusion -> HIGH alert)")

    # Case 3: Concordant findings (cardiomegaly present in both) -> 0 alerts
    t0 = time.perf_counter()
    vf_3 = [{"label": "cardiomegaly", "score": 0.85, "negated": False, "neg_score": 0.15}]
    te_3 = [{"snippet": "Enlarged cardiac silhouette consistent with cardiomegaly.", "source_id": "doc_rad_003", "category": "radiology"}]
    alerts_3 = detect_discrepancies(vf_3, te_3)
    lat_3 = (time.perf_counter() - t0) * 1000

    assert len(alerts_3) == 0, f"Expected 0 alerts, got {len(alerts_3)}"

    results.append({
        "test_name": "test_matching_concordant_findings_no_alert",
        "description": "Concordant visual and textual evidence produces 0 alerts",
        "status": "PASSED",
        "latency_ms": round(lat_3, 3),
        "inputs": {"visual_findings": vf_3, "text_evidence": te_3},
        "output_alerts": [],
    })
    logger.info("  ✅ Case 3 Passed: Concordant findings -> 0 alerts")

    # Case 4: Sub-threshold visual finding (<0.60) -> 0 alerts
    t0 = time.perf_counter()
    vf_4 = [{"label": "pneumothorax", "score": 0.42, "negated": False, "neg_score": 0.58}]
    te_4 = [{"snippet": "No pneumothorax is identified on the current view.", "source_id": "doc_rad_004", "category": "radiology"}]
    alerts_4 = detect_discrepancies(vf_4, te_4)
    lat_4 = (time.perf_counter() - t0) * 1000

    assert len(alerts_4) == 0, f"Expected 0 alerts, got {len(alerts_4)}"

    results.append({
        "test_name": "test_subthreshold_visual_finding_no_alert",
        "description": "Sub-threshold visual confidence (< 0.60) does not trigger alert",
        "status": "PASSED",
        "latency_ms": round(lat_4, 3),
        "inputs": {"visual_findings": vf_4, "text_evidence": te_4},
        "output_alerts": [],
    })
    logger.info("  ✅ Case 4 Passed: Sub-threshold visual score -> 0 alerts")

    # Case 5: Fail-open on empty or malformed inputs
    t0 = time.perf_counter()
    assert detect_discrepancies([], []) == []
    assert detect_discrepancies(None, None) == []
    assert detect_discrepancies([{"invalid": True}], [{"invalid": True}]) == []
    lat_5 = (time.perf_counter() - t0) * 1000

    results.append({
        "test_name": "test_fail_open_on_empty_or_invalid",
        "description": "Fail-open behavior produces empty list without raising exceptions",
        "status": "PASSED",
        "latency_ms": round(lat_5, 3),
        "inputs": {"empty_lists": True, "none_inputs": True, "malformed_dicts": True},
        "output_alerts": [],
    })
    logger.info("  ✅ Case 5 Passed: Fail-open safety check passed")

    return {
        "feature": "F1_CROSS_MODAL_DISCREPANCY_GUARDRAIL",
        "total_tests": len(results),
        "passed_tests": sum(1 for r in results if r["status"] == "PASSED"),
        "failed_tests": 0,
        "average_latency_ms": round(sum(r["latency_ms"] for r in results) / len(results), 3),
        "test_cases": results,
    }


def run_knowledge_gap_tests() -> Dict[str, Any]:
    logger.info("\n--- Running F2: Epistemic Knowledge-Gap Mapper Test Suite ---")
    results = []

    # Case 1: G1 Corpus retrieval gap (fused score < 0.02)
    t0 = time.perf_counter()
    q_1 = "What is the recommended dosage for investigational kinase inhibitor ABX-492?"
    ret_1 = [{"chunk_id": "chunk_001", "document_id": "doc_general", "fused_score": 0.009}]
    gaps_1 = map_knowledge_gaps(query=q_1, retrieved_items=ret_1, phi=0.40, answer_status="refusal")
    lat_1 = (time.perf_counter() - t0) * 1000

    g1_list = [g for g in gaps_1 if g.gap_type == "corpus_retrieval"]
    assert len(g1_list) >= 1, "Expected at least 1 corpus_retrieval gap"
    assert "below relevance threshold" in g1_list[0].detail
    assert len(g1_list[0].suggested_queries) >= 1
    assert len(g1_list[0].suggested_sources) >= 1

    results.append({
        "test_name": "test_corpus_retrieval_gap_low_fused_score",
        "description": "G1: Top fused score < 0.02 triggers corpus_retrieval gap with reformulations",
        "status": "PASSED",
        "latency_ms": round(lat_1, 3),
        "inputs": {"query": q_1, "retrieved_items": ret_1, "phi": 0.40, "answer_status": "refusal"},
        "output_gaps": [g.model_dump() for g in gaps_1],
    })
    logger.info("  ✅ Case 1 Passed: G1 Corpus retrieval gap detected with suggested queries & sources")

    # Case 2: G2 Graph coverage gap (neutral graph check / missing relation)
    t0 = time.perf_counter()
    q_2 = "Does warfarin interact with St Johns Wort in atrial fibrillation?"
    ret_2 = [{"chunk_id": "chunk_002", "document_id": "doc_warfarin", "fused_score": 0.08}]
    gc_2 = {"verdict": "neutral", "reason": "No direct graph assertion linking warfarin to herbal supplement via INTERACTS_WITH"}
    gaps_2 = map_knowledge_gaps(query=q_2, retrieved_items=ret_2, graph_checks=gc_2, phi=0.60, answer_status="uncertain")
    lat_2 = (time.perf_counter() - t0) * 1000

    g2_list = [g for g in gaps_2 if g.gap_type == "graph_coverage"]
    assert len(g2_list) >= 1, "Expected at least 1 graph_coverage gap"
    assert "graph" in g2_list[0].detail.lower()
    assert any("UMLS" in s or "DrugBank" in s for s in g2_list[0].suggested_sources)

    results.append({
        "test_name": "test_graph_coverage_gap_neutral_check",
        "description": "G2: Neutral graph check triggers graph_coverage gap with relation suggestions",
        "status": "PASSED",
        "latency_ms": round(lat_2, 3),
        "inputs": {"query": q_2, "retrieved_items": ret_2, "graph_checks": gc_2, "phi": 0.60, "answer_status": "uncertain"},
        "output_gaps": [g.model_dump() for g in gaps_2],
    })
    logger.info("  ✅ Case 2 Passed: G2 Graph coverage gap detected with UMLS/DrugBank guidance")

    # Case 3: G3 Faithfulness gap (phi < 0.50)
    t0 = time.perf_counter()
    q_3 = "Can metformin be safely prescribed in end-stage renal failure with eGFR < 15?"
    ret_3 = [{"chunk_id": "chunk_003", "document_id": "doc_metformin_guidelines", "fused_score": 0.12}]
    gaps_3 = map_knowledge_gaps(query=q_3, retrieved_items=ret_3, phi=0.32, answer_status="refusal")
    lat_3 = (time.perf_counter() - t0) * 1000

    g3_list = [g for g in gaps_3 if g.gap_type == "evidence_faithfulness"]
    assert len(g3_list) >= 1, "Expected at least 1 evidence_faithfulness gap"
    assert "0.32" in g3_list[0].detail
    assert any("doc_metformin_guidelines" in sq for sq in g3_list[0].suggested_queries)

    results.append({
        "test_name": "test_evidence_faithfulness_gap_low_phi",
        "description": "G3: Low faithfulness score (phi < 0.50) triggers evidence_faithfulness gap",
        "status": "PASSED",
        "latency_ms": round(lat_3, 3),
        "inputs": {"query": q_3, "retrieved_items": ret_3, "phi": 0.32, "answer_status": "refusal"},
        "output_gaps": [g.model_dump() for g in gaps_3],
    })
    logger.info("  ✅ Case 3 Passed: G3 Evidence faithfulness gap detected with primary source referral")

    # Case 4: High confidence / verified query -> 0 gaps
    t0 = time.perf_counter()
    q_4 = "warfarin INR monitoring guidelines"
    ret_4 = [{"chunk_id": "chunk_004", "document_id": "doc_inr_guideline", "fused_score": 0.22}]
    gaps_4 = map_knowledge_gaps(query=q_4, retrieved_items=ret_4, phi=0.92, answer_status="verified")
    lat_4 = (time.perf_counter() - t0) * 1000

    assert len(gaps_4) == 0, f"Expected 0 gaps for verified query, got {len(gaps_4)}"

    results.append({
        "test_name": "test_verified_high_confidence_produces_no_gaps",
        "description": "Verified, high-faithfulness query execution produces zero knowledge gaps",
        "status": "PASSED",
        "latency_ms": round(lat_4, 3),
        "inputs": {"query": q_4, "retrieved_items": ret_4, "phi": 0.92, "answer_status": "verified"},
        "output_gaps": [],
    })
    logger.info("  ✅ Case 4 Passed: Verified query produces 0 gaps")

    # Case 5: Fail-open on empty or None input
    t0 = time.perf_counter()
    assert map_knowledge_gaps(query="") == []
    assert map_knowledge_gaps(query="test", retrieved_items=None) == []
    lat_5 = (time.perf_counter() - t0) * 1000

    results.append({
        "test_name": "test_fail_open_on_none_input",
        "description": "Fail-open behavior safely handles None and missing arguments",
        "status": "PASSED",
        "latency_ms": round(lat_5, 3),
        "inputs": {"empty_query": True, "none_retrieval": True},
        "output_gaps": [],
    })
    logger.info("  ✅ Case 5 Passed: Fail-open safety check passed")

    return {
        "feature": "F2_EPISTEMIC_KNOWLEDGE_GAP_MAPPER",
        "total_tests": len(results),
        "passed_tests": sum(1 for r in results if r["status"] == "PASSED"),
        "failed_tests": 0,
        "average_latency_ms": round(sum(r["latency_ms"] for r in results) / len(results), 3),
        "test_cases": results,
    }


def main():
    logger.info("=" * 80)
    logger.info("MEDGRAPHRAG — STEP 19: GUARDRAILS & EPISTEMIC GAPS EVALUATION")
    logger.info("=" * 80)

    t_start = time.time()
    f1_report = run_discrepancy_tests()
    f2_report = run_knowledge_gap_tests()
    total_time_s = round(time.time() - t_start, 4)

    total_passed = f1_report["passed_tests"] + f2_report["passed_tests"]
    total_tests = f1_report["total_tests"] + f2_report["total_tests"]

    final_report = {
        "step": "Step 19",
        "description": "Cross-Modal Discrepancy Guardrail (F1) & Epistemic Knowledge-Gap Mapper (F2) Evaluation Report",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_duration_s": total_time_s,
        "summary": {
            "total_test_suites": 2,
            "total_test_cases": total_tests,
            "passed_test_cases": total_passed,
            "failed_test_cases": 0,
            "pass_rate_pct": round((total_passed / total_tests) * 100, 2),
            "status": "ALL_TESTS_PASSED",
        },
        "features": {
            "F1_CROSS_MODAL_DISCREPANCY_GUARDRAIL": f1_report,
            "F2_EPISTEMIC_KNOWLEDGE_GAP_MAPPER": f2_report,
        },
    }

    report_bytes = json.dumps(final_report, indent=2, sort_keys=True).encode("utf-8")
    report_sha256 = hashlib.sha256(report_bytes).hexdigest()
    final_report["artifact_sha256"] = report_sha256

    out_path = _PROJECT_ROOT / "evaluations" / "step19_guardrails_eval_report.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(final_report, f, indent=2, sort_keys=True)

    logger.info("\n" + "=" * 80)
    logger.info("EVALUATION COMPLETE: %d/%d TESTS PASSED (100%%)", total_passed, total_tests)
    logger.info("Saved JSON Report → %s (SHA-256: %s)", out_path, report_sha256)
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
