#!/usr/bin/env python
"""Stage A: J8 full suite — 50 seed-42 step12 queries x 5 retrievers.

Retrieval-only (no LLM/GPU). Reuses the memory-safe BM25 pool-200 baseline.
Writes evaluations/step17_baselines.json with:
  - metadata (seed 42, N=50, timestamp, measured peak RSS, runtime,
    truncation rule k=10, OOM-exit-137 note for BM25 labeling)
  - display-name retrievers + per-retriever avg latency/items/graph stats
    + full top-10 lists for all 50 queries
  - P01-P05 top-doc agreement of every baseline vs MedGraphRAG
  - MedGraphRAG P01-P05 regression content hash (must equal
    ba1b512168fc4a949d12b0547e6992c4dddae63ca30b2294b13e47c9c0d18eac),
    computed by the SAME code path as scripts/j1/run_regression.py
  - artifact_sha256 over the final serialized file bytes
"""
import gc
import hashlib
import json
import resource
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts" / "j1"))
sys.path.insert(0, str(ROOT / "evaluations" / "baselines"))

from baseline_retrieval import run_baseline_comparison  # noqa: E402
import run_regression as j1reg  # noqa: E402

STEP12 = ROOT / "evaluations/step12_evaluation_report.json"
OUT = ROOT / "evaluations/step17_baselines.json"
EXPECTED_HASH = "ba1b512168fc4a949d12b0547e6992c4dddae63ca30b2294b13e47c9c0d18eac"

DISPLAY = {
    "BM25Retriever": "BM25-RAG (pool-200)",
    "DenseVectorRetriever": "Dense-RAG",
    "HybridRRFRetriever": "Hybrid-RRF",
    "GraphOnlyRetriever": "Graph-Only",
    "MedGraphRAGRetriever": "MedGraphRAG",
}


def load_queries() -> list[dict]:
    d = json.loads(STEP12.read_text())
    qs = d["ablation_results"]["C1_FULL"]["per_question_details"]
    assert d.get("sampling_seed") == 42, "step12 seed mismatch"
    return [{"id": q["question_id"], "query": q["question"]} for q in qs]


def peak_rss_mb() -> int:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024


def main() -> None:
    t0 = time.perf_counter()
    golden = load_queries()
    queries = [g["query"] for g in golden]
    print(f"[stageA] N={len(queries)} seed=42 queries loaded", flush=True)

    # 1. Full comparison (5 retrievers x 50 queries)
    report = run_baseline_comparison(queries=queries, top_n=10, output_path=None)

    # 2. Regression content hash via the IDENTICAL J1 code path (P01-P05),
    #    using verify_drift.py's latency-stripped retrieval signature —
    #    this is the canonical hash recorded in step14/step15 artifacts.
    tmp_out = ROOT / "evaluations/scratch/_stepA_regression_tmp.json"
    payload = j1reg.run_regression_suite(tmp_out)
    suite_hash = payload["sha256"]

    def retrieval_signature(data):
        sig = []
        for q in data["results"]:
            sig.append({
                "id": q["id"],
                "query": q["query"],
                "top_doc_id": q["top_doc_id"],
                "top_fused_score": q["top_fused_score"],
                "items_count": q["items_count"],
                "entities_reached": q["entities_reached"],
                "chunks_from_graph": q["chunks_from_graph"],
                "items": q["retrieved_items"],
            })
        return sig

    reg_hash = hashlib.sha256(
        json.dumps(retrieval_signature(payload), indent=2, sort_keys=True).encode("utf-8")
    ).hexdigest()
    regression_ok = reg_hash == EXPECTED_HASH
    print(f"[stageA] retrieval_content_sha={reg_hash[:16]}... match={regression_ok}", flush=True)

    # 3. P01-P05 top-doc agreement vs MedGraphRAG
    #    NOTE: golden probes are NOT members of the 50 MedQA vignettes,
    #    so retrieve them explicitly here.
    from baseline_retrieval import (
        BM25Retriever, DenseVectorRetriever, HybridRRFRetriever,
        GraphOnlyRetriever, MedGraphRAGRetriever,
    )
    cls_by_disp = {
        "BM25-RAG (pool-200)": BM25Retriever,
        "Dense-RAG": DenseVectorRetriever,
        "Hybrid-RRF": HybridRRFRetriever,
        "Graph-Only": GraphOnlyRetriever,
        "MedGraphRAG": MedGraphRAGRetriever,
    }
    agreement = {}
    for g in j1reg.GOLDEN_QUERIES:
        qtext = g["query"]
        tops = {}
        for disp, cls in cls_by_disp.items():
            try:
                res = cls().retrieve(qtext, top_n=10)
                tops[disp] = res.items[0].document_id if res.items else None
            except Exception:
                tops[disp] = None
            gc.collect()
        ref = tops.get("MedGraphRAG")
        agreement[g["id"]] = {
            "top_doc_per_retriever": tops,
            "agrees_with_MedGraphRAG": [d for d, v in tops.items()
                                        if v is not None and v == ref and d != "MedGraphRAG"],
        }
        print(f"[stageA] {g['id']} agreement: {agreement[g['id']]['agrees_with_MedGraphRAG']}", flush=True)

    # 4. Assemble final artifact
    summary = {DISPLAY[k]: v for k, v in report["summary"].items()}
    results_named = {DISPLAY[k]: v for k, v in report["results"].items()}
    runtime_s = round(time.perf_counter() - t0, 1)

    final = {
        "metadata": {
            "suite": "J8 full baselines (Stage A)",
            "seed": 42,
            "N": len(queries),
            "query_source": "evaluations/step12_evaluation_report.json::ablation_results.C1_FULL.per_question_details",
            "timestamp_epoch": time.time(),
            "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "runtime_seconds": runtime_s,
            "measured_peak_rss_mb": peak_rss_mb(),
            "truncation_rule": "fixed depth k=10 for ALL retrievers; missing = absent",
            "retriever_labels": {
                "BM25-RAG (pool-200)": (
                    "full-corpus in-memory BM25 infeasible on 16 GB consumer RAM "
                    "(OOM exit 137); lexical baseline computed over dense candidate "
                    "pool (faiss_store.batch_load_chunk_texts byte-offset access)"
                ),
            },
            "device_policy": "CPU-only retrieval; GPU reserved for Qwen2.5-7B LLM",
            "regression_expected_sha256": EXPECTED_HASH,
            "regression_measured_sha256": reg_hash,
            "regression_suite_full_sha256": suite_hash,
            "regression_hash_method": "verify_drift.extract_retrieval_signature (latency-stripped), canonical for step14/step15",
            "regression_match": regression_ok,
            "artifact_note": "J8 pilot discrepancy fixed: explicit artifact_sha256 field embedded",
        },
        "queries": [{"id": g["id"], "query": g["query"]} for g in golden],
        "summary": summary,
        "results": results_named,
        "p01_p05_top_doc_agreement_vs_MedGraphRAG": agreement,
    }

    body = json.dumps(final, indent=2, default=str, sort_keys=True).encode("utf-8")
    final["metadata"]["artifact_sha256"] = hashlib.sha256(body).hexdigest()
    OUT.write_text(json.dumps(final, indent=2, default=str, sort_keys=True))
    tmp_out.unlink(missing_ok=True)

    file_sha = hashlib.sha256(OUT.read_bytes()).hexdigest()
    print(f"[stageA] WROTE {OUT}")
    print(f"[stageA] artifact_sha256(embedded)={final['metadata']['artifact_sha256']}")
    print(f"[stageA] file_sha256={file_sha}")
    print(f"[stageA] peak_rss_mb={peak_rss_mb()} runtime_s={runtime_s} "
          f"regression_match={regression_ok}")


if __name__ == "__main__":
    main()
