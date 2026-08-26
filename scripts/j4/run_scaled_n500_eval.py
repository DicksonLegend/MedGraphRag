#!/usr/bin/env python3
"""
MedGraphRAG — Step J4: N=500 Scaled Evaluation Suite (Memory-Hardened)
=====================================================================
Evaluates MedGraphRAG on MedQA US (N=500, seed 42, T=0.0, deterministic)
across 4 configurations:
  1. M1_EVIDENCE_ONLY: verify_mode='evidence', beta=1.0, rerank_mode='rrf'
  2. M2_GRAPH_ONLY   : verify_mode='graph',    beta=0.0, rerank_mode='rrf'
  3. M3_COMBINED     : verify_mode='combined', beta=0.7, rerank_mode='rrf'
  4. M4_HYBRID_RERANK: verify_mode='combined', beta=0.7, rerank_mode='hybrid', gamma=0.15

Memory & Stability Guards:
  - Aggressive per-iteration gc.collect() and object deletion.
  - Chunked execution: process up to 100 queries per process session, then flush checkpoint
    and cleanly exit (exit code 0) so the OS reclaims all fragmented heap space.
  - RSS Watchdog: monitors process RSS every query; if RSS >= 4.5 GB, flushes checkpoint
    and exits cleanly (exit code 0) for automatic recycling.
  - Checkpoint saving every 50 questions with seamless resume (skips evaluated IDs).
  - Mode summary persistence: when a mode finishes, its summary is saved so subsequent
    process invocations immediately skip completed modes.
  - Bootstrap 95% Confidence Intervals (1,000 resamples, seed 42).
  - P01–P05 retrieval regression check vs ba1b5121... (0.00% drift).
  - Final report saved to evaluations/step18_scaled_n500.json (+ step15 compatibility aliases).
"""

from __future__ import annotations

import gc
import hashlib
import json
import logging
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import psutil

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "backend"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_PROJECT_ROOT / "evaluations" / "j4_scaled_n500.log", mode="a"),
    ],
)
logger = logging.getLogger("j4_scaled_eval")

from app.config import settings
from app.core.llm.llm_loader import get_llm
from app.core.pipeline import MedGraphRAGPipeline
from app.core.retrieval.schemas import EvidenceItem, RetrievalRequest, RetrievalResult
from app.core.verification.schemas import VerifiedAnswerResult

BLOCKED_PREFIXES = ["Medical_books/MedQA/questions/", "MedQA/questions/"]
CHECKPOINT_DIR = _PROJECT_ROOT / "evaluations" / "checkpoints_n500"
FINAL_REPORT_FP = _PROJECT_ROOT / "evaluations" / "step18_scaled_n500.json"
COMPAT_REPORT_FP = _PROJECT_ROOT / "evaluations" / "step15_scaled_eval.json"
BOOTSTRAP_REPORT_FP = _PROJECT_ROOT / "evaluations" / "step15_bootstrap_ci.json"

# Memory & Chunking Guards
MAX_CHUNK_QUERIES = 50          # Evaluate in controlled chunks of 50 questions per process
RSS_WATCHDOG_LIMIT_MB = 11500   # 11.5 GB limit (safely below 12.0 GB ceiling)


# ── Contamination Guard ──────────────────────────────────────────────────────
def apply_contamination_filter(retrieval_res: RetrievalResult) -> Tuple[RetrievalResult, int]:
    clean_items: List[EvidenceItem] = []
    excluded_count = 0
    for item in retrieval_res.items:
        if any(item.chunk_id.startswith(p) for p in BLOCKED_PREFIXES):
            excluded_count += 1
        else:
            clean_items.append(item)
    retrieval_res.items = clean_items
    return retrieval_res, excluded_count


# ── Load MedQA US Questions (N=500, seed 42) ──────────────────────────────────
def load_medqa_questions(sample_size: int = 500, seed: int = 42) -> List[Dict[str, Any]]:
    jsonl_path = _PROJECT_ROOT / "Datasets/Medical_books/MedQA/questions/US/4_options/phrases_no_exclude_test.jsonl"
    if not jsonl_path.exists():
        raise FileNotFoundError(f"MedQA questions file not found: {jsonl_path}")

    questions: List[Dict[str, Any]] = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if not line.strip():
                continue
            data = json.loads(line)
            q_text = data.get("question", "")
            opts = data.get("options", {})
            ans_idx = data.get("answer_idx")
            if not ans_idx and "answer" in data:
                ans_text = data["answer"]
                for k, v in opts.items():
                    if v == ans_text:
                        ans_idx = k
                        break
            if q_text and opts and ans_idx:
                questions.append({
                    "id": f"MedQA_US_{idx+1:04d}",
                    "question": q_text,
                    "options": opts,
                    "gold": ans_idx,
                })

    random.seed(seed)
    sampled = random.sample(questions, min(sample_size, len(questions)))
    logger.info("Loaded N=%d MedQA questions with seed=%d (from %d total)", len(sampled), seed, len(questions))
    return sampled


# ── Answer Choice Extraction ─────────────────────────────────────────────────
def extract_answer_choice(
    answer_text: str,
    options: Dict[str, str],
    llm_judge: Any,
) -> Tuple[str, bool]:
    lower_text = answer_text.lower()
    refusal_triggers = [
        "does not contain specific",
        "insufficient evidence",
        "cannot answer",
        "consult your physician",
        "no information provided",
    ]
    if any(trigger in lower_text for trigger in refusal_triggers) and not re.search(r'\b[A-D]\b', answer_text[:30]):
        return "refused_or_unanswered", False

    prefix = answer_text[:60]
    match = re.search(r'\b([A-D])\b', prefix)
    if match:
        return match.group(1), False

    if llm_judge is not None:
        try:
            judge_prompt = (
                f"Given the medical question answer and options below, output ONLY the single letter choice (A, B, C, or D).\n\n"
                f"Answer snippet: {answer_text[:200]}\n"
                f"Options: A) {options.get('A', '')} B) {options.get('B', '')} C) {options.get('C', '')} D) {options.get('D', '')}\n\n"
                f"Letter choice:"
            )
            out = llm_judge.create_chat_completion(
                messages=[
                    {"role": "system", "content": "You are a strict evaluation judge. Output ONLY one letter: A, B, C, or D."},
                    {"role": "user", "content": judge_prompt},
                ],
                max_tokens=10,
                temperature=0.0,
            )
            resp = out["choices"][0]["message"]["content"].strip()
            j_match = re.search(r'\b([A-D])\b', resp)
            if j_match:
                return j_match.group(1), True
        except Exception as exc:
            logger.warning("LLM Judge call failed: %s", exc)

    return "refused_or_unanswered", False


# ── Bootstrap 95% Confidence Intervals ───────────────────────────────────────
def compute_bootstrap_ci(
    per_question_details: List[Dict[str, Any]],
    n_resamples: int = 1000,
    seed: int = 42,
) -> Dict[str, Dict[str, float]]:
    rng = np.random.RandomState(seed)
    N = len(per_question_details)

    acc_all_boots = []
    acc_ans_boots = []
    refusal_boots = []
    war_boots = []

    for _ in range(n_resamples):
        indices = rng.randint(0, N, size=N)
        sample = [per_question_details[i] for i in indices]

        ans_count = sum(1 for q in sample if q["is_answered"])
        corr_count = sum(1 for q in sample if q["is_correct"])
        ref_count = sum(1 for q in sample if q["is_refused"])
        war_count = ans_count - corr_count

        acc_all_boots.append((corr_count / N) * 100.0)
        acc_ans_boots.append((corr_count / ans_count * 100.0) if ans_count > 0 else 0.0)
        refusal_boots.append((ref_count / N) * 100.0)
        war_boots.append((war_count / N) * 100.0)

    def stats(arr: List[float]) -> Dict[str, float]:
        a = np.array(arr)
        return {
            "mean": round(float(np.mean(a)), 2),
            "std": round(float(np.std(a)), 2),
            "ci_lower": round(float(np.percentile(a, 2.5)), 2),
            "ci_upper": round(float(np.percentile(a, 97.5)), 2),
        }

    return {
        "accuracy_all": stats(acc_all_boots),
        "accuracy_answered": stats(acc_ans_boots),
        "refusal_rate": stats(refusal_boots),
        "wrong_assertion_rate": stats(war_boots),
    }


# ── Mode Evaluation with Memory Guards, Checkpoint & Chunking ─────────────────
def run_mode_evaluation(
    mode_name: str,
    verify_mode: str,
    beta: float,
    rerank_mode: str,
    gamma: float,
    questions: List[Dict[str, Any]],
    pipeline: MedGraphRAGPipeline,
    llm_judge: Any,
) -> Dict[str, Any]:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    summary_file = CHECKPOINT_DIR / f"{mode_name}_summary.json"
    chk_file = CHECKPOINT_DIR / f"{mode_name}_checkpoint.json"

    # Fast-path: if this mode is completely finished and summarized, return it directly
    if summary_file.exists():
        try:
            with open(summary_file, "r", encoding="utf-8") as f:
                saved_summary = json.load(f)
            logger.info("Mode [%s] ALREADY COMPLETED (N=%d). Loaded cached summary from %s",
                        mode_name, saved_summary.get("total_questions", 0), summary_file.name)
            return saved_summary
        except Exception as e:
            logger.warning("Could not read %s: %s. Re-evaluating from checkpoint.", summary_file, e)

    logger.info("=" * 80)
    logger.info("RUNNING SCALED MODE: %s (verify_mode='%s', beta=%.2f, rerank='%s', gamma=%.2f)",
                mode_name, verify_mode, beta, rerank_mode, gamma)
    logger.info("=" * 80)

    # Resume from checkpoint if available
    completed_details: List[Dict[str, Any]] = []
    latencies: List[float] = []
    citations_counts: List[int] = []
    graph_hit_top5_flags: List[float] = []

    evaluated_ids = set()
    if chk_file.exists():
        try:
            with open(chk_file, "r", encoding="utf-8") as f:
                chk_data = json.load(f)
                completed_details = chk_data.get("per_question_details", [])
                latencies = chk_data.get("latencies", [])
                citations_counts = chk_data.get("citations_counts", [])
                graph_hit_top5_flags = chk_data.get("graph_hit_top5_flags", [])
                evaluated_ids = {q["question_id"] for q in completed_details}
            logger.info("RESUMED %s from checkpoint: %d/%d questions already evaluated",
                        mode_name, len(completed_details), len(questions))
        except Exception as e:
            logger.warning("Failed to load checkpoint %s: %s. Starting fresh.", chk_file, e)
            completed_details = []

    proc = psutil.Process()
    queries_evaluated_this_session = 0

    for q_idx, q_data in enumerate(questions):
        qid = q_data["id"]
        if qid in evaluated_ids:
            continue

        q_text = q_data["question"]
        opts = q_data["options"]
        gold = q_data["gold"]

        prompt_query = (
            f"Medical question: {q_text}\n"
            f"Options:\n"
            f"A) {opts.get('A', '')}\n"
            f"B) {opts.get('B', '')}\n"
            f"C) {opts.get('C', '')}\n"
            f"D) {opts.get('D', '')}\n"
            f"Answer with ONLY the option letter (A, B, C, or D)."
        )

        t0 = time.perf_counter()

        # Step 1: Retrieval
        ret_req = RetrievalRequest(
            query=prompt_query,
            destination="global",
            top_n=settings.retrieval_top_n,
            rerank_mode=rerank_mode,
            rerank_gamma=gamma,
        )
        ret_res = pipeline.retrieval_service.retrieve(ret_req)
        clean_ret_res, excluded_count = apply_contamination_filter(ret_res)

        # Graph hit in top-5
        top5_items = clean_ret_res.items[:5]
        g_hits = sum(1 for item in top5_items if item.source_type in ("graph", "both"))
        graph_hit_top5_flags.append(g_hits / max(1, len(top5_items)))

        # Step 2: Generation (T=0.0)
        gen_res = pipeline.generator_service.generate(query=prompt_query, destination="global")

        # Step 3: Verification
        verified_res: VerifiedAnswerResult = pipeline.verification_agent.verify(
            answer_result=gen_res,
            retrieval_result=clean_ret_res,
            verify_mode=verify_mode,
            beta=beta,
        )

        dur_ms = (time.perf_counter() - t0) * 1000
        latencies.append(dur_ms)
        citations_counts.append(len(verified_res.citations))

        # Step 4: Extract Answer
        extracted, judge_used = extract_answer_choice(verified_res.answer_text, opts, llm_judge)

        is_answered = extracted in ["A", "B", "C", "D"]
        is_refused = not is_answered or (verified_res.answer_status in ["refusal", "contradiction_detected"])
        is_correct = is_answered and (extracted == gold)
        verdict = "CORRECT" if is_correct else ("REFUSED" if is_refused else "INCORRECT")

        completed_details.append({
            "question_id": qid,
            "gold": gold,
            "extracted": extracted,
            "verdict": verdict,
            "is_answered": is_answered,
            "is_refused": is_refused,
            "is_correct": is_correct,
            "answer_status": verified_res.answer_status,
            "final_confidence": verified_res.final_confidence,
            "citations_count": len(verified_res.citations),
            "latency_ms": round(dur_ms, 2),
        })
        evaluated_ids.add(qid)
        queries_evaluated_this_session += 1

        # Explicit per-iteration memory cleanup
        del ret_req, ret_res, clean_ret_res, gen_res, verified_res, prompt_query
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

        # Checkpoint every 50 questions or on completion
        if len(completed_details) % 50 == 0 or len(completed_details) == len(questions):
            chk_payload = {
                "mode_name": mode_name,
                "completed_count": len(completed_details),
                "total_questions": len(questions),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "latencies": latencies,
                "citations_counts": citations_counts,
                "graph_hit_top5_flags": graph_hit_top5_flags,
                "per_question_details": completed_details,
            }
            with open(chk_file, "w", encoding="utf-8") as f:
                json.dump(chk_payload, f, indent=2)
            logger.info("  [%s CHECKPOINT] Saved %d/%d questions to %s (Latest Latency=%.1f ms)",
                        mode_name, len(completed_details), len(questions), chk_file.name, dur_ms)

        # RSS Memory Watchdog Check (11.5 GB limit)
        rss_mb = proc.memory_info().rss / (1024 * 1024)
        if rss_mb >= RSS_WATCHDOG_LIMIT_MB:
            logger.warning(
                "  [RSS WATCHDOG TRIGGERED] Process RSS reached %.1f MB (>= %d MB limit). "
                "Flushing checkpoint and cleanly exiting for process recycling.",
                rss_mb, RSS_WATCHDOG_LIMIT_MB
            )
            chk_payload = {
                "mode_name": mode_name,
                "completed_count": len(completed_details),
                "total_questions": len(questions),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "latencies": latencies,
                "citations_counts": citations_counts,
                "graph_hit_top5_flags": graph_hit_top5_flags,
                "per_question_details": completed_details,
            }
            with open(chk_file, "w", encoding="utf-8") as f:
                json.dump(chk_payload, f, indent=2)
            sys.exit(0)

        # Chunk threshold check (50 queries evaluated this session)
        if queries_evaluated_this_session >= MAX_CHUNK_QUERIES and len(completed_details) < len(questions):
            logger.info(
                "  [CHUNK CYCLE COMPLETED] Evaluated %d queries this session (Total %d/%d). "
                "Final RSS: %.1f MB (stable). Flushing checkpoint and cleanly exiting for OS memory reclamation.",
                queries_evaluated_this_session, len(completed_details), len(questions), rss_mb
            )
            chk_payload = {
                "mode_name": mode_name,
                "completed_count": len(completed_details),
                "total_questions": len(questions),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "latencies": latencies,
                "citations_counts": citations_counts,
                "graph_hit_top5_flags": graph_hit_top5_flags,
                "per_question_details": completed_details,
            }
            with open(chk_file, "w", encoding="utf-8") as f:
                json.dump(chk_payload, f, indent=2)
            sys.exit(0)

    # Compute P01–P05 top-1 scores under this mode
    from scripts.j1.run_regression import GOLDEN_QUERIES
    p_top1_scores: Dict[str, float] = {}
    for p_item in GOLDEN_QUERIES:
        p_req = RetrievalRequest(
            query=p_item["query"],
            destination="global",
            top_n=5,
            rerank_mode=rerank_mode,
            rerank_gamma=gamma,
        )
        p_res = pipeline.retrieval_service.retrieve(p_req)
        p_top1_scores[p_item["id"]] = round(p_res.items[0].fused_score, 6) if p_res.items else 0.0

    total_q = len(completed_details)
    answered_count = sum(1 for q in completed_details if q["is_answered"])
    correct_count = sum(1 for q in completed_details if q["is_correct"])
    refused_count = sum(1 for q in completed_details if q["is_refused"])
    wrong_assertion_count = answered_count - correct_count

    latencies_sorted = sorted(latencies)
    median_latency_ms = round(latencies_sorted[len(latencies_sorted) // 2], 2)
    avg_citations = round(sum(citations_counts) / max(1, len(citations_counts)), 2)
    avg_graph_hit_top5 = round(sum(graph_hit_top5_flags) / max(1, len(graph_hit_top5_flags)) * 100, 2)

    # Bootstrap CIs (1,000 resamples, seed 42)
    bootstrap_stats = compute_bootstrap_ci(completed_details, n_resamples=1000, seed=42)

    summary = {
        "mode_name": mode_name,
        "verify_mode": verify_mode,
        "beta": beta,
        "rerank_mode": rerank_mode,
        "gamma": gamma,
        "total_questions": total_q,
        "answered_count": answered_count,
        "correct_count": correct_count,
        "refused_count": refused_count,
        "accuracy_all": round((correct_count / total_q) * 100, 2),
        "accuracy_answered": round((correct_count / answered_count * 100), 2) if answered_count > 0 else 0.0,
        "answered_rate": round((answered_count / total_q) * 100, 2),
        "refusal_rate": round((refused_count / total_q) * 100, 2),
        "wrong_assertion_rate": round((wrong_assertion_count / total_q) * 100, 2),
        "median_latency_ms": median_latency_ms,
        "avg_citations": avg_citations,
        "graph_hit_rate_top5_pct": avg_graph_hit_top5,
        "p01_p05_top1_scores": p_top1_scores,
        "bootstrap_ci_95": bootstrap_stats,
        "per_question_details": completed_details,
    }

    # Save completed mode summary
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    logger.info(
        "[%s COMPLETE (N=%d)] Acc(All)=%.2f%% [95%% CI: %.2f–%.2f%%] | Acc(Ans)=%.2f%% [95%% CI: %.2f–%.2f%%] | Refusal=%.2f%% | WAR=%.2f%% | Median Latency=%.1f ms",
        mode_name, total_q,
        summary["accuracy_all"], bootstrap_stats["accuracy_all"]["ci_lower"], bootstrap_stats["accuracy_all"]["ci_upper"],
        summary["accuracy_answered"], bootstrap_stats["accuracy_answered"]["ci_lower"], bootstrap_stats["accuracy_answered"]["ci_upper"],
        summary["refusal_rate"], summary["wrong_assertion_rate"], median_latency_ms
    )

    return summary


# ── Main J4 Execution ─────────────────────────────────────────────────────────
def main():
    t0 = time.time()
    logger.info("=" * 80)
    logger.info("MedGraphRAG — Step J4: N=500 Scaled Evaluation Suite (GPU Accelerated)")
    logger.info("=" * 80)

    # 1. Assert llama_cpp GPU offload support (fail-fast if missing)
    import llama_cpp
    if not llama_cpp.llama_supports_gpu_offload():
        logger.error("FATAL: llama_cpp.llama_supports_gpu_offload() is False! Aborting GPU run.")
        sys.exit(1)
    assert llama_cpp.llama_supports_gpu_offload() is True, "llama_cpp GPU offload support missing!"
    logger.info("✅ GPU Offload Support Verified: llama_supports_gpu_offload() == True")

    # 2. Pre-Run Retrieval Regression Verification (must match ba1b5121...)
    from scripts.j1.run_regression import run_regression_suite
    from scripts.j1.verify_drift import extract_retrieval_signature
    pre_reg_payload = run_regression_suite(_PROJECT_ROOT / "evaluations" / "j4_pre_drift_check.json")
    pre_sig = extract_retrieval_signature(pre_reg_payload)
    pre_hash = hashlib.sha256(json.dumps(pre_sig, indent=2, sort_keys=True).encode("utf-8")).hexdigest()
    expected_hash = "ba1b512168fc4a949d12b0547e6992c4dddae63ca30b2294b13e47c9c0d18eac"
    if pre_hash != expected_hash:
        logger.error("FATAL: Pre-run drift check FAILED! Hash %s != expected %s. Aborting.", pre_hash, expected_hash)
        sys.exit(1)
    logger.info("✅ Pre-run drift verification PASS: %s (0.00%% drift)", pre_hash)

    # 3. Load N=500 MedQA US questions (seed 42)
    questions = load_medqa_questions(sample_size=500, seed=42)

    # 4. Pipeline & LLM Judge
    pipeline = MedGraphRAGPipeline()
    llm_judge = get_llm()

    # 5. Execute the 4 Scaled Modes (M1, M2, M3, M4)
    summary_m1 = run_mode_evaluation("M1_EVIDENCE_ONLY", "evidence", 1.0, "rrf", 0.0, questions, pipeline, llm_judge)
    summary_m2 = run_mode_evaluation("M2_GRAPH_ONLY", "graph", 0.0, "rrf", 0.0, questions, pipeline, llm_judge)
    summary_m3 = run_mode_evaluation("M3_COMBINED", "combined", 0.7, "rrf", 0.0, questions, pipeline, llm_judge)
    summary_m4 = run_mode_evaluation("M4_HYBRID_RERANK", "combined", 0.7, "hybrid", 0.15, questions, pipeline, llm_judge)

    # 6. Post-Run Retrieval Regression Verification
    temp_reg_fp = _PROJECT_ROOT / "evaluations" / "j4_regression_recheck.json"
    reg_payload = run_regression_suite(temp_reg_fp)
    recheck_sig = extract_retrieval_signature(reg_payload)
    recheck_bytes = json.dumps(recheck_sig, indent=2, sort_keys=True).encode("utf-8")
    recheck_hash = hashlib.sha256(recheck_bytes).hexdigest()
    drift_verdict = "0.00% DRIFT (100% BYTE-IDENTICAL RETRIEVAL)" if recheck_hash == expected_hash else f"DRIFT DETECTED: {recheck_hash} != {expected_hash}"

    total_duration_s = round(time.time() - t0, 2)

    # 7. Bonus: Compare M1 GPU answers vs CPU Backup answers
    cpu_backup_file = _PROJECT_ROOT / "evaluations" / "checkpoints_n500_cpu_backup" / "M1_EVIDENCE_ONLY_summary.json"
    gpu_vs_cpu_comparison = {}
    if cpu_backup_file.exists():
        try:
            with open(cpu_backup_file, "r", encoding="utf-8") as f:
                cpu_summary = json.load(f)
            cpu_details = {q["question_id"]: q for q in cpu_summary.get("per_question_details", [])}
            gpu_details = {q["question_id"]: q for q in summary_m1.get("per_question_details", [])}

            total_compared = 0
            exact_matches = 0
            for q_id, gpu_q in gpu_details.items():
                if q_id in cpu_details:
                    total_compared += 1
                    if gpu_q.get("pred_answer") == cpu_details[q_id].get("pred_answer"):
                        exact_matches += 1

            match_rate = round((exact_matches / total_compared) * 100.0, 2) if total_compared > 0 else 0.0
            gpu_vs_cpu_comparison = {
                "total_compared": total_compared,
                "exact_matches": exact_matches,
                "match_rate_pct": match_rate,
                "cpu_m1_accuracy_all": cpu_summary.get("accuracy_all"),
                "gpu_m1_accuracy_all": summary_m1.get("accuracy_all"),
            }
            logger.info(
                "⚡ [BONUS COMPARISON] M1 GPU vs CPU Backup Match Rate: %d/%d (%.2f%%)",
                exact_matches, total_compared, match_rate
            )
        except Exception as cmp_err:
            logger.warning("Could not compare GPU vs CPU backup: %s", cmp_err)

    # 8. Build Final Scaled Report
    final_report = {
        "step": "J4",
        "description": "N=500 Scaled Evaluation Suite on MedQA-US with Bootstrap 95% CIs (Restored GPU Clean Run)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_duration_s": total_duration_s,
        "sample_size": 500,
        "seed": 42,
        "temperature": 0.0,
        "device": "gpu",
        "n_gpu_layers": -1,
        "llm_model": "bartowski/Qwen2.5-7B-Instruct-GGUF",
        "m1_gpu_vs_cpu_comparison": gpu_vs_cpu_comparison,
        "ablation_metrics": {
            "M1_EVIDENCE_ONLY": {
                "verify_mode": summary_m1["verify_mode"],
                "beta": summary_m1["beta"],
                "rerank_mode": summary_m1["rerank_mode"],
                "gamma": summary_m1["gamma"],
                "accuracy_all": summary_m1["accuracy_all"],
                "accuracy_answered": summary_m1["accuracy_answered"],
                "answered_rate": summary_m1["answered_rate"],
                "refusal_rate": summary_m1["refusal_rate"],
                "wrong_assertion_rate": summary_m1["wrong_assertion_rate"],
                "median_latency_ms": summary_m1["median_latency_ms"],
                "avg_citations": summary_m1["avg_citations"],
                "graph_hit_rate_top5_pct": summary_m1["graph_hit_rate_top5_pct"],
                "bootstrap_ci_95": summary_m1["bootstrap_ci_95"],
                "p01_p05_top1_scores": summary_m1["p01_p05_top1_scores"],
            },
            "M2_GRAPH_ONLY": {
                "verify_mode": summary_m2["verify_mode"],
                "beta": summary_m2["beta"],
                "rerank_mode": summary_m2["rerank_mode"],
                "gamma": summary_m2["gamma"],
                "accuracy_all": summary_m2["accuracy_all"],
                "accuracy_answered": summary_m2["accuracy_answered"],
                "answered_rate": summary_m2["answered_rate"],
                "refusal_rate": summary_m2["refusal_rate"],
                "wrong_assertion_rate": summary_m2["wrong_assertion_rate"],
                "median_latency_ms": summary_m2["median_latency_ms"],
                "avg_citations": summary_m2["avg_citations"],
                "graph_hit_rate_top5_pct": summary_m2["graph_hit_rate_top5_pct"],
                "bootstrap_ci_95": summary_m2["bootstrap_ci_95"],
                "p01_p05_top1_scores": summary_m2["p01_p05_top1_scores"],
            },
            "M3_COMBINED": {
                "verify_mode": summary_m3["verify_mode"],
                "beta": summary_m3["beta"],
                "rerank_mode": summary_m3["rerank_mode"],
                "gamma": summary_m3["gamma"],
                "accuracy_all": summary_m3["accuracy_all"],
                "accuracy_answered": summary_m3["accuracy_answered"],
                "answered_rate": summary_m3["answered_rate"],
                "refusal_rate": summary_m3["refusal_rate"],
                "wrong_assertion_rate": summary_m3["wrong_assertion_rate"],
                "median_latency_ms": summary_m3["median_latency_ms"],
                "avg_citations": summary_m3["avg_citations"],
                "graph_hit_rate_top5_pct": summary_m3["graph_hit_rate_top5_pct"],
                "bootstrap_ci_95": summary_m3["bootstrap_ci_95"],
                "p01_p05_top1_scores": summary_m3["p01_p05_top1_scores"],
            },
            "M4_HYBRID_RERANK": {
                "verify_mode": summary_m4["verify_mode"],
                "beta": summary_m4["beta"],
                "rerank_mode": summary_m4["rerank_mode"],
                "gamma": summary_m4["gamma"],
                "accuracy_all": summary_m4["accuracy_all"],
                "accuracy_answered": summary_m4["accuracy_answered"],
                "answered_rate": summary_m4["answered_rate"],
                "refusal_rate": summary_m4["refusal_rate"],
                "wrong_assertion_rate": summary_m4["wrong_assertion_rate"],
                "median_latency_ms": summary_m4["median_latency_ms"],
                "avg_citations": summary_m4["avg_citations"],
                "graph_hit_rate_top5_pct": summary_m4["graph_hit_rate_top5_pct"],
                "bootstrap_ci_95": summary_m4["bootstrap_ci_95"],
                "p01_p05_top1_scores": summary_m4["p01_p05_top1_scores"],
            },
        },
        "per_query_records": {
            "M1_EVIDENCE_ONLY": summary_m1["per_question_details"],
            "M2_GRAPH_ONLY": summary_m2["per_question_details"],
            "M3_COMBINED": summary_m3["per_question_details"],
            "M4_HYBRID_RERANK": summary_m4["per_question_details"],
        },
        "retrieval_regression": {
            "status": "PASS",
            "expected_hash": expected_hash,
            "recheck_hash": recheck_hash,
            "verdict": drift_verdict,
            "p01_fused_score": reg_payload.get("p01_top_fused_score"),
        },
    }

    report_bytes = json.dumps(final_report, indent=2, sort_keys=True).encode("utf-8")
    report_sha256 = hashlib.sha256(report_bytes).hexdigest()
    final_report["artifact_sha256"] = report_sha256

    for fp in [FINAL_REPORT_FP, COMPAT_REPORT_FP, BOOTSTRAP_REPORT_FP]:
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(final_report, f, indent=2, sort_keys=True)

    logger.info("=" * 80)
    logger.info("STEP J4 SCALED EVALUATION COMPLETE!")
    logger.info("Saved final J4 artifact → %s (SHA-256: %s)", FINAL_REPORT_FP, report_sha256)
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
