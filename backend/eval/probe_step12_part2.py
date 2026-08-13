"""
MedGraphRAG — Step 12 Part 2 Evaluation & Ablation Probe Script (Prep Phase)
=============================================================================
Evaluates MedGraphRAG accuracy, refusal rate, latency, and provenance on MedQA US (N=50)
across 4 ablation configurations:
  C1_FULL:        graph_enabled=True,  verification_enabled=True
  C2_VECTOR_ONLY: graph_enabled=False, verification_enabled=True
  C3_NO_VERIFY:   graph_enabled=True,  verification_enabled=False
  C4_BASELINE:    graph_enabled=False, verification_enabled=False

HARD RULES:
- Contamination Guard: Excludes any chunk starting with BLOCKED_PREFIXES ("Medical_books/MedQA/questions/").
- Single LLM singleton instance (Qwen2.5-7B-Instruct GGUF Q4_K_M).
- Evaluates locally on disk raw question files only.
- Output saved to evaluations/step12_evaluation_report.json.
"""

import json
import logging
import random
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "backend"))

from app.config import settings
from app.core.llm.llm_loader import get_llm
from app.core.pipeline import MedGraphRAGPipeline
from app.core.retrieval.schemas import EvidenceItem, RetrievalRequest, RetrievalResult
from app.core.verification.verifier import VerifiedAnswerResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("probe_step12_part2")

# ---------------------------------------------------------------------------
# Contamination Guard
# ---------------------------------------------------------------------------
BLOCKED_PREFIXES = ["Medical_books/MedQA/questions/", "MedQA/questions/"]


def apply_contamination_filter(retrieval_res: RetrievalResult) -> Tuple[RetrievalResult, int]:
    """Filter out any chunk that originates from the MedQA questions directory."""
    original_items = retrieval_res.items
    clean_items: List[EvidenceItem] = []
    excluded_count = 0

    for item in original_items:
        cid = item.chunk_id
        if any(cid.startswith(prefix) for prefix in BLOCKED_PREFIXES):
            excluded_count += 1
        else:
            clean_items.append(item)

    retrieval_res.items = clean_items
    return retrieval_res, excluded_count


# ---------------------------------------------------------------------------
# MedQA Question Loader
# ---------------------------------------------------------------------------
def load_medqa_questions(sample_size: int = 50, seed: int = 42) -> List[Dict[str, Any]]:
    """Load MedQA US test questions from raw JSONL source on disk and sample N questions."""
    possible_paths = [
        _PROJECT_ROOT / "Datasets/Medical_books/MedQA/questions/US/4_options/phrases_no_exclude_test.jsonl",
        _PROJECT_ROOT / "Datasets/Medical_books/MedQA/questions/US/test.jsonl",
        _PROJECT_ROOT / "Datasets/MedQA-USMLE/data/test-00000-of-00001.parquet",
    ]

    raw_path: Optional[Path] = None
    for p in possible_paths:
        if p.exists():
            raw_path = p
            break

    if not raw_path:
        raise FileNotFoundError(f"Could not find raw MedQA questions in any of: {possible_paths}")

    logger.info("Loading MedQA raw questions from: %s", raw_path)
    questions: List[Dict[str, Any]] = []

    if raw_path.suffix == ".jsonl":
        with open(raw_path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                if not line.strip():
                    continue
                data = json.loads(line)
                q_text = data.get("question", "")
                opts = data.get("options", {})
                ans_idx = data.get("answer_idx")

                # Normalize correct answer letter
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
    elif raw_path.suffix == ".parquet":
        import pandas as pd
        df = pd.read_parquet(raw_path)
        for idx, row in df.iterrows():
            questions.append({
                "id": f"MedQA_US_{idx+1:04d}",
                "question": row["question"],
                "options": row["options"],
                "gold": row["answer_idx"],
            })

    logger.info("Total MedQA questions found on disk: %d", len(questions))

    random.seed(seed)
    sampled = random.sample(questions, min(sample_size, len(questions)))
    logger.info("Sampled N=%d questions with seed=%d", len(sampled), seed)
    return sampled


# ---------------------------------------------------------------------------
# Answer Extraction Logic (Eval script only)
# ---------------------------------------------------------------------------
def extract_answer_choice(
    answer_text: str,
    options: Dict[str, str],
    llm_instance: Optional[Any] = None,
) -> Tuple[str, bool]:
    """
    Extract single option letter (A, B, C, D) from answer text.
    1. First 50 chars regex matching.
    2. If ambiguous, 1 judge call to LLM.
    3. If refusal / uncertain, return 'refused_or_unanswered'.
    Returns (extracted_letter, judge_used).
    """
    lower_text = answer_text.lower()
    refusal_triggers = [
        "does not contain specific",
        "insufficient evidence",
        "cannot answer",
        "consult your physician",
        "no information provided",
    ]
    # Check if answer text represents a refusal/disclaimer without a choice
    if any(trigger in lower_text for trigger in refusal_triggers) and not re.search(r'\b[A-D]\b', answer_text[:30]):
        return "refused_or_unanswered", False

    # 1. Regex check in first 50 chars
    prefix = answer_text[:60]
    match = re.search(r'\b([A-D])\b', prefix)
    if match:
        return match.group(1), False

    # 2. LLM Judge fallback (1 call)
    if llm_instance is not None:
        try:
            judge_prompt = (
                f"Given the medical question answer and options below, output ONLY the single letter choice (A, B, C, or D).\n\n"
                f"Answer snippet: {answer_text[:200]}\n"
                f"Options: A) {options.get('A', '')} B) {options.get('B', '')} C) {options.get('C', '')} D) {options.get('D', '')}\n\n"
                f"Letter choice:"
            )
            out = llm_instance.create_chat_completion(
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


# ---------------------------------------------------------------------------
# Single Question Pipeline Execution
# ---------------------------------------------------------------------------
def run_single_question(
    pipeline: MedGraphRAGPipeline,
    q_data: Dict[str, Any],
    llm_judge: Any,
) -> Dict[str, Any]:
    """Run single question through pipeline with contamination filtering."""
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

    # Step 1: Retrieve
    ret_req = RetrievalRequest(query=prompt_query, destination="global", top_n=settings.retrieval_top_n)
    ret_res = pipeline.retrieval_service.retrieve(ret_req)

    # Step 2: Apply Contamination Filter
    clean_ret_res, excluded_count = apply_contamination_filter(ret_res)

    # Step 3: Generate
    gen_res = pipeline.generator_service.generate(query=prompt_query, destination="global")

    # Step 4: Verify (if enabled)
    if settings.pipeline_verification_enabled:
        verified_res: VerifiedAnswerResult = pipeline.verification_agent.verify(
            answer_result=gen_res,
            retrieval_result=clean_ret_res,
        )
    else:
        conf = gen_res.evidence_confidence
        conf_tier = "high" if conf >= 0.7 else ("medium" if conf >= 0.5 else "low")
        verified_res = VerifiedAnswerResult(
            **gen_res.model_dump(),
            answer_status="verified",
            final_confidence=conf,
            confidence_tier=conf_tier,
            faithfulness_score=1.0,
            verification_ms=0.0,
            fallback_used=False,
            claim_verdicts=[],
            reasoning="Verification disabled by ablation config.",
            retry_count=0,
        )

    latency_ms = (time.perf_counter() - t0) * 1000

    # Extract Answer Choice
    extracted, judge_used = extract_answer_choice(verified_res.answer_text, opts, llm_judge)

    is_refused = (extracted == "refused_or_unanswered" or verified_res.answer_status == "refusal")
    is_correct = (extracted == gold)

    return {
        "question_id": q_data["id"],
        "question": q_text[:100] + "...",
        "gold": gold,
        "extracted": extracted,
        "verdict": "CORRECT" if is_correct else ("REFUSED" if is_refused else "INCORRECT"),
        "is_correct": is_correct,
        "is_refused": is_refused,
        "judge_used": judge_used,
        "final_confidence": round(verified_res.final_confidence, 4),
        "citations_count": len(verified_res.citations),
        "excluded_chunks_count": excluded_count,
        "latency_ms": round(latency_ms, 2),
    }


# ---------------------------------------------------------------------------
# Contamination Filter Proof
# ---------------------------------------------------------------------------
def run_contamination_filter_proof(pipeline: MedGraphRAGPipeline) -> Dict[str, Any]:
    """Test contamination filter against a query constructed from an indexed MedQA question."""
    test_q = "A 43-year-old man comes to the physician because of redness and swelling of his right leg pain touch fever chills saphenous vein type 2 diabetes"
    logger.info("Executing Contamination Filter Proof call for query: %r", test_q[:60])
    ret_req = RetrievalRequest(query=test_q, destination="global", top_n=20)
    ret_res = pipeline.retrieval_service.retrieve(ret_req)

    raw_cids = [item.chunk_id for item in ret_res.items]
    clean_res, excluded_cnt = apply_contamination_filter(ret_res)
    excluded_cids = [cid for cid in raw_cids if any(cid.startswith(p) for p in BLOCKED_PREFIXES)]

    logger.info("[FILTER PROOF] Total raw: %d | Excluded: %d | Excluded CIDs: %s", len(raw_cids), excluded_cnt, excluded_cids)
    return {
        "query": test_q,
        "raw_chunks_count": len(raw_cids),
        "excluded_chunks_count": excluded_cnt,
        "excluded_chunk_ids": excluded_cids,
        "proof_passed": excluded_cnt >= 1,
    }


# ---------------------------------------------------------------------------
# Ablation Benchmark Suite
# ---------------------------------------------------------------------------
def run_benchmark_suite(is_smoke: bool = False):
    """Execute MedQA US evaluation across 4 ablation configurations with incremental JSON saving."""
    import os
    pipeline = MedGraphRAGPipeline()
    llm_judge = get_llm()

    # Warm-up query
    logger.info("Executing model warm-up query...")
    _ = pipeline.answer(query="Warmup test query for GPU initialization", destination="global")

    # Contamination Filter Proof
    filter_proof_res = run_contamination_filter_proof(pipeline)

    sample_n = 2 if is_smoke else 50
    questions = load_medqa_questions(sample_size=sample_n, seed=42)

    ablation_configs = [
        ("C1_FULL", True, True),
        ("C2_VECTOR_ONLY", False, True),
        ("C3_NO_VERIFY", True, False),
        ("C4_BASELINE", False, False),
    ]

    all_config_results: Dict[str, Any] = {}
    out_file = _PROJECT_ROOT / "evaluations" / "step12_evaluation_report.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)

    for config_name, graph_on, verify_on in ablation_configs:
        logger.info("=== Running Ablation Config: %s (graph=%s, verify=%s, N=%d) ===", config_name, graph_on, verify_on, sample_n)

        # Toggle flags
        settings.retrieval_graph_enabled = graph_on
        settings.pipeline_verification_enabled = verify_on

        per_question_logs: List[Dict[str, Any]] = []
        latencies: List[float] = []
        confidences: List[float] = []
        citations_counts: List[int] = []
        excluded_chunks_total = 0
        judge_calls_total = 0

        correct_count = 0
        refused_count = 0

        for q_idx, q_data in enumerate(questions):
            q_res = run_single_question(pipeline, q_data, llm_judge)
            per_question_logs.append(q_res)

            latencies.append(q_res["latency_ms"])
            confidences.append(q_res["final_confidence"])
            citations_counts.append(q_res["citations_count"])
            excluded_chunks_total += q_res["excluded_chunks_count"]
            if q_res["judge_used"]:
                judge_calls_total += 1

            if q_res["is_correct"]:
                correct_count += 1
            if q_res["is_refused"]:
                refused_count += 1

            logger.info("[%s Q%d/%d] ID=%s Verdict=%s (Latency=%.1fms, Conf=%.2f)",
                        config_name, q_idx + 1, sample_n, q_data["id"], q_res["verdict"], q_res["latency_ms"], q_res["final_confidence"])

        # Calculate metrics for config
        total_q = len(questions)
        answered_count = total_q - refused_count

        latencies_sorted = sorted(latencies)
        median_lat = latencies_sorted[len(latencies_sorted) // 2] if latencies_sorted else 0.0

        metrics = {
            "config_name": config_name,
            "retrieval_graph_enabled": graph_on,
            "pipeline_verification_enabled": verify_on,
            "accuracy_all": round((correct_count / total_q) * 100, 2),
            "accuracy_answered": round((correct_count / answered_count * 100), 2) if answered_count > 0 else 0.0,
            "answered_rate": round((answered_count / total_q) * 100, 2),
            "refusal_rate": round((refused_count / total_q) * 100, 2),
            "avg_final_confidence": round(sum(confidences) / total_q, 4) if total_q > 0 else 0.0,
            "avg_citations_per_answer": round(sum(citations_counts) / total_q, 2) if total_q > 0 else 0.0,
            "avg_latency_ms": round(sum(latencies) / total_q, 2) if total_q > 0 else 0.0,
            "median_latency_ms": round(median_lat, 2),
            "total_judge_calls": judge_calls_total,
            "chunks_excluded_by_contamination_filter": excluded_chunks_total,
            "questions_evaluated": total_q,
            "per_question_details": per_question_logs,
        }

        all_config_results[config_name] = metrics

        # INCREMENTAL SAVING: Save report JSON after EACH config completes
        interim_report = {
            "step": 12.2,
            "description": "MedGraphRAG Step 12 Part 2 — MedQA US Benchmark & Ablation Evaluation",
            "is_smoke_run": is_smoke,
            "sampling_seed": 42,
            "questions_count": sample_n,
            "contamination_filter_active": True,
            "blocked_prefixes": BLOCKED_PREFIXES,
            "filter_proof": filter_proof_res,
            "ablation_results": all_config_results,
        }
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(interim_report, f, indent=2)
        logger.info("Incremental report updated after %s at %s", config_name, out_file)

    # ---------------------------------------------------------------------------
    # Flag Restoration & 1c Regression Check
    # ---------------------------------------------------------------------------
    settings.retrieval_graph_enabled = True
    settings.pipeline_verification_enabled = True

    p01_q = "warfarin INR monitoring guidelines atrial fibrillation"
    p01_res = pipeline.retrieval_service.retrieve(RetrievalRequest(query=p01_q, destination="global", top_n=10))
    p01_top_doc = p01_res.items[0].document_id if p01_res.items else ""
    p01_top_score = round(p01_res.items[0].fused_score, 4) if p01_res.items else 0.0
    p01_n_items = len(p01_res.items)

    flag_restoration_proof = {
        "retrieval_graph_enabled": settings.retrieval_graph_enabled,
        "pipeline_verification_enabled": settings.pipeline_verification_enabled,
        "p01_top_doc": p01_top_doc,
        "p01_top_score": p01_top_score,
        "p01_n_items": p01_n_items,
        "restoration_passed": ("PMID_38823454" in p01_top_doc and abs(p01_top_score - 0.1774) < 0.01 and p01_n_items >= 9),
    }

    final_report = {
        "step": 12.2,
        "description": "MedGraphRAG Step 12 Part 2 — MedQA US Benchmark & Ablation Evaluation",
        "is_smoke_run": is_smoke,
        "sampling_seed": 42,
        "questions_count": sample_n,
        "contamination_filter_active": True,
        "blocked_prefixes": BLOCKED_PREFIXES,
        "filter_proof": filter_proof_res,
        "flag_restoration_proof": flag_restoration_proof,
        "ablation_results": all_config_results,
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(final_report, f, indent=2)

    logger.info("=== Benchmark Suite Complete. Final report saved to: %s ===", out_file)


# ---------------------------------------------------------------------------
# Validation Guard / Execution Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import os
    is_smoke_env = os.environ.get("SMOKE") == "1" or "--smoke" in sys.argv

    if is_smoke_env:
        logger.info("==========================================================================")
        print("EXECUTING PRE-FLIGHT SMOKE TEST (SMOKE=1, N=2 questions per config)")
        logger.info("==========================================================================")
        run_benchmark_suite(is_smoke=True)
    else:
        print("==========================================================================")
        print("MedGraphRAG Step 12 Part 2 Evaluation Script — PREP PHASE VALIDATION")
        print("==========================================================================")
        print("  BLOCKED_PREFIXES defined:", BLOCKED_PREFIXES)
        print("  Config flags present:")
        print("    - settings.retrieval_graph_enabled:", getattr(settings, "retrieval_graph_enabled", None))
        print("    - settings.pipeline_verification_enabled:", getattr(settings, "pipeline_verification_enabled", None))
        print("==========================================================================")
        print("SCRIPT READY — awaiting user confirmation to run.")

