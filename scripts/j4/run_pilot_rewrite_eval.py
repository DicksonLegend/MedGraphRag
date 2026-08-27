#!/usr/bin/env python3
"""
MedGraphRAG — Step 2: Pilot Query Rewriting Evaluation (N=50, seed 42)
=====================================================================
Tests whether clinical query rewriting improves Acc(all) on N=50 MedQA vignettes
for M4 (Hybrid Rerank) and M3 (Combined).

Pilot Gate Rule:
  Proceed to full N=500 re-run only if Acc(all) improves by >= +10 points absolute.
"""

from __future__ import annotations

import gc
import json
import logging
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "backend"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("pilot_rewrite_eval")

from app.config import settings
from app.core.llm.llm_loader import get_llm
from app.core.pipeline import MedGraphRAGPipeline
from app.core.retrieval.query_rewrite import rewrite_clinical_query
from app.core.retrieval.schemas import EvidenceItem, RetrievalRequest, RetrievalResult
from app.core.verification.schemas import VerifiedAnswerResult

BLOCKED_PREFIXES = ["Medical_books/MedQA/questions/", "MedQA/questions/"]


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


def load_medqa_questions(sample_size: int = 50, seed: int = 42) -> List[Dict[str, Any]]:
    jsonl_path = _PROJECT_ROOT / "Datasets/Medical_books/MedQA/questions/US/4_options/phrases_no_exclude_test.jsonl"
    questions = []
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
    logger.info("Loaded N=%d pilot MedQA questions with seed=%d", len(sampled), seed)
    return sampled


def extract_answer_choice(
    answer_text: str,
    options: Dict[str, str],
    llm_judge: Any,
) -> Tuple[str, bool]:
    # Strip standard disclaimers and uncertainty headers before inspecting choice
    cleaned = answer_text
    cleaned = re.sub(r'⚠️.*?guidance\.\s*', '', cleaned, flags=re.DOTALL)
    cleaned = re.sub(r'This is information, not medical advice.*?physician\.', '', cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip()

    lower_text = cleaned.lower()
    refusal_triggers = [
        "does not contain specific",
        "insufficient evidence",
        "cannot answer",
        "no information provided",
        "evidence provided does not",
    ]
    if any(trigger in lower_text for trigger in refusal_triggers) and not re.search(r'\b[A-D]\b', cleaned[:30]):
        return "refused_or_unanswered", False

    prefix = cleaned[:60]
    match = re.search(r'\b([A-D])\b', prefix)
    if match:
        return match.group(1), False

    alt_match = re.search(r'(?:option|choice|answer)\s*[:\s\-]*([A-D])\b', cleaned, re.IGNORECASE)
    if alt_match:
        return alt_match.group(1).upper(), False

    if llm_judge is not None:
        try:
            judge_prompt = (
                f"Given the medical question answer and options below, output ONLY the single letter choice (A, B, C, or D).\n\n"
                f"Answer snippet: {cleaned[:200]}\n"
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


def evaluate_mode_pilot(
    mode_name: str,
    verify_mode: str,
    beta: float,
    rerank_mode: str,
    gamma: float,
    questions: List[Dict[str, Any]],
    pipeline: MedGraphRAGPipeline,
    llm: Any,
) -> Dict[str, Any]:
    logger.info("=" * 80)
    logger.info("RUNNING PILOT MODE: %s (verify_mode='%s', beta=%.2f, rerank='%s', gamma=%.2f)",
                mode_name, verify_mode, beta, rerank_mode, gamma)
    logger.info("=" * 80)

    per_question_details = []
    latencies = []

    for q_idx, q_data in enumerate(questions):
        qid = q_data["id"]
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

        # Step 0: Clinical Query Rewriting
        rewritten_q = rewrite_clinical_query(raw_query=q_text, max_words=30, llm_instance=llm)

        # Step 1: Retrieval with Rewritten Query
        ret_req = RetrievalRequest(
            query=rewritten_q,
            destination="global",
            top_n=settings.retrieval_top_n,
            rerank_mode=rerank_mode,
            rerank_gamma=gamma,
        )
        ret_res = pipeline.retrieval_service.retrieve(ret_req)
        clean_ret_res, _ = apply_contamination_filter(ret_res)

        # Step 2: Generation with Full Prompt
        gen_res = pipeline.generator_service.generate(
            query=prompt_query,
            destination="global",
            retrieval_result=clean_ret_res,
        )

        # Step 3: Verification
        verified_res: VerifiedAnswerResult = pipeline.verification_agent.verify(
            answer_result=gen_res,
            retrieval_result=clean_ret_res,
            verify_mode=verify_mode,
            beta=beta,
        )

        dur_ms = (time.perf_counter() - t0) * 1000
        latencies.append(dur_ms)

        pred_choice, judged = extract_answer_choice(verified_res.answer_text, opts, llm)
        is_refused = (
            verified_res.answer_status in ("refusal", "out_of_scope", "error")
            or pred_choice == "refused_or_unanswered"
            or (verified_res.final_confidence < 0.50 and verified_res.answer_status != "verified")
        )
        is_correct = (not is_refused) and (pred_choice == gold)
        is_answered = not is_refused

        per_question_details.append({
            "question_id": qid,
            "raw_question": q_text[:100] + "...",
            "rewritten_query": rewritten_q,
            "gold": gold,
            "pred": pred_choice,
            "is_refused": is_refused,
            "is_answered": is_answered,
            "is_correct": is_correct,
            "final_confidence": verified_res.final_confidence,
            "faithfulness_score": verified_res.faithfulness_score,
            "answer_status": verified_res.answer_status,
            "latency_ms": round(dur_ms, 2),
        })

        logger.info(
            "[%s] Q%02d/%02d (%s) | Pred: %s, Gold: %s | Correct: %s, Refused: %s | Conf: %.3f | Latency: %.1f ms",
            mode_name, q_idx + 1, len(questions), qid, pred_choice, gold, is_correct, is_refused, verified_res.final_confidence, dur_ms
        )

        gc.collect()

    N = len(per_question_details)
    ans_count = sum(1 for q in per_question_details if q["is_answered"])
    corr_count = sum(1 for q in per_question_details if q["is_correct"])
    ref_count = sum(1 for q in per_question_details if q["is_refused"])
    war_count = ans_count - corr_count

    acc_all = round((corr_count / N) * 100.0, 2)
    acc_ans = round((corr_count / ans_count * 100.0) if ans_count > 0 else 0.0, 2)
    ref_rate = round((ref_count / N) * 100.0, 2)
    war = round((war_count / N) * 100.0, 2)
    med_lat = round(float(np.median(latencies)), 2) if latencies else 0.0

    return {
        "mode_name": mode_name,
        "sample_size": N,
        "accuracy_all": acc_all,
        "accuracy_answered": acc_ans,
        "refusal_rate": ref_rate,
        "wrong_assertion_rate": war,
        "median_latency_ms": med_lat,
        "per_question_details": per_question_details,
    }


def main():
    import numpy as np
    logger.info("Initializing MedGraphRAG Pipeline on GPU for Pilot (N=50)...")
    llm = get_llm()
    pipeline = MedGraphRAGPipeline()

    questions = load_medqa_questions(sample_size=50, seed=42)

    # 1. Run M4_HYBRID_RERANK
    m4_res = evaluate_mode_pilot(
        mode_name="M4_HYBRID_RERANK_REWRITE",
        verify_mode="combined",
        beta=0.7,
        rerank_mode="hybrid",
        gamma=0.15,
        questions=questions,
        pipeline=pipeline,
        llm=llm,
    )

    # 2. Run M3_COMBINED
    m3_res = evaluate_mode_pilot(
        mode_name="M3_COMBINED_REWRITE",
        verify_mode="combined",
        beta=0.7,
        rerank_mode="rrf",
        gamma=0.0,
        questions=questions,
        pipeline=pipeline,
        llm=llm,
    )

    pilot_report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sample_size": 50,
        "seed": 42,
        "device": "gpu",
        "results": {
            "M4_HYBRID_RERANK": m4_res,
            "M3_COMBINED": m3_res,
        },
    }

    out_file = _PROJECT_ROOT / "evaluations" / "j4_pilot_rewrite_report.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(pilot_report, f, indent=2)

    logger.info("\n" + "=" * 80)
    logger.info("PILOT EVALUATION SUMMARY (N=50, seed 42, With Query Rewriting)")
    logger.info("=" * 80)
    logger.info("M4: Acc(All)=%.2f%% | Acc(Ans)=%.2f%% | WAR=%.2f%% | Refusal=%.2f%% | Med Lat=%.1f ms",
                m4_res["accuracy_all"], m4_res["accuracy_answered"], m4_res["wrong_assertion_rate"], m4_res["refusal_rate"], m4_res["median_latency_ms"])
    logger.info("M3: Acc(All)=%.2f%% | Acc(Ans)=%.2f%% | WAR=%.2f%% | Refusal=%.2f%% | Med Lat=%.1f ms",
                m3_res["accuracy_all"], m3_res["accuracy_answered"], m3_res["wrong_assertion_rate"], m3_res["refusal_rate"], m3_res["median_latency_ms"])
    logger.info("Saved pilot artifact -> %s", out_file)


if __name__ == "__main__":
    main()
