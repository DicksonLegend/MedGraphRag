#!/usr/bin/env python
"""Phase 2C+2D: retrieve top-10 for the 30 phase-2 queries with the SAME
MedGraphRAG fused config as step17, embed a P01-P05 regression check, and emit
the blank two-assessor grading sheet.

Outputs:
  evaluations/phase2_retrieval.json     (retrieval results + regression block)
  evaluations/phase2_grading_sheet.tsv  (300 rows; grade_A/grade_B blank)
Read-only wrt index/global/* and kuzu_db_v5.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts" / "j1"))
sys.path.insert(0, str(ROOT / "evaluations" / "baselines"))

from baseline_retrieval import MedGraphRAGRetriever  # noqa: E402
import run_regression as j1reg  # noqa: E402

QUERIES = json.loads((ROOT / "evaluations/phase2_queries.json").read_text())["queries"]
OUT_R = ROOT / "evaluations/phase2_retrieval.json"
OUT_T = ROOT / "evaluations/phase2_grading_sheet.tsv"
EXPECTED_HASH = "ba1b512168fc4a949d12b0547e6992c4dddae63ca30b2294b13e47c9c0d18eac"
P01_EXPECTED = 0.177352


def retrieval_signature(data):
    return [{
        "id": q["id"], "query": q["query"], "top_doc_id": q["top_doc_id"],
        "top_fused_score": q["top_fused_score"], "items_count": q["items_count"],
        "entities_reached": q["entities_reached"],
        "chunks_from_graph": q["chunks_from_graph"], "items": q["retrieved_items"],
    } for q in data["results"]]


def resolve_texts(chunk_ids):
    """chunk_id -> first ~200 chars of chunk text via sidecar + byte-offsets."""
    import pyarrow.parquet as pq
    t = pq.read_table(ROOT / "index/global/id_mapping.parquet",
                      columns=["faiss_id", "chunk_id"])
    cid2fid = {c: f for f, c in zip(t["faiss_id"].to_pylist(),
                                    t["chunk_id"].to_pylist()) if c in chunk_ids}
    from app.core.retrieval import faiss_store
    faiss_store.warm_up()
    texts = faiss_store.batch_load_chunk_texts(
        [cid2fid[c] for c in chunk_ids if c in cid2fid])
    out = {}
    for cid in chunk_ids:
        fid = cid2fid.get(cid)
        if fid is not None and fid in texts:
            out[cid] = texts[fid][:200].replace("\t", " ").replace("\n", " ")
    return out


def main() -> None:
    t0 = time.perf_counter()

    # ── Regression guard: P01–P05 through the identical j1 code path ──
    payload = j1reg.run_regression_suite(
        ROOT / "evaluations/scratch/_phase2_regression_tmp.json")
    sig_hash = hashlib.sha256(json.dumps(
        retrieval_signature(payload), indent=2, sort_keys=True).encode()).hexdigest()
    p01 = next(q for q in payload["results"] if q["id"] == "P01")
    regression_pass = sig_hash == EXPECTED_HASH and \
        abs(p01["top_fused_score"] - P01_EXPECTED) <= 5e-6
    print(f"[p2] regression: hash_match={sig_hash == EXPECTED_HASH} "
          f"p01={p01['top_fused_score']} pass={regression_pass}", flush=True)

    # ── Retrieval over the 30 phase-2 queries ──
    ret = MedGraphRAGRetriever()
    per_query, flat_rows, all_cids = [], [], []
    for i, q in enumerate(QUERIES, 1):
        res = ret.retrieve(q["query"], top_n=10)
        items = [{"rank": r + 1,
                  "chunk_id": it.chunk_id,
                  "document_id": it.document_id,
                  "category": it.category,
                  "fused_score": round(it.fused_score, 6)}
                 for r, it in enumerate(res.items)]
        per_query.append({"query_id": q["id"], "query": q["query"], "items": items})
        for it in items:
            all_cids.append(it["chunk_id"])
        print(f"[p2] {q['id']} ({i}/{len(QUERIES)}) items={len(items)}", flush=True)

    # ── Determinism proof: re-run Q11 and compare byte-equal ──
    res_again = ret.retrieve(QUERIES[10]["query"], top_n=10)
    again = [(it.chunk_id, round(it.fused_score, 6)) for it in res_again.items]
    first = [(it["chunk_id"], it["fused_score"]) for it in per_query[10]["items"]]
    deterministic = again == first
    print(f"[p2] determinism rerun match={deterministic}", flush=True)

    texts = resolve_texts(set(all_cids))

    doc_r = {
        "stage": "PHASE2_retrieval",
        "config": "MedGraphRAGRetriever (HybridRetrievalService), top_n=10, destination=global — same as step17_baselines",
        "n_queries": len(QUERIES),
        "deterministic_rerun_match": deterministic,
        "regression_check": {
            "method": "scripts/j1/run_regression.py + verify_drift.extract_retrieval_signature",
            "p01_top_fused_score": p01["top_fused_score"],
            "p01_expected": P01_EXPECTED,
            "signature_hash": sig_hash,
            "expected_hash": EXPECTED_HASH,
            "pass": regression_pass,
        },
        "queries": per_query,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    body_sha = hashlib.sha256(
        json.dumps(doc_r, indent=2).encode()).hexdigest()
    doc_r["artifact_sha256"] = body_sha
    OUT_R.write_text(json.dumps(doc_r, indent=2))

    # ── Grading sheet TSV ──
    lines = ["query_id\tquery\trank\tchunk_id\tdocument_id\tcategory\t"
             "fused_score\tchunk_text\tgrade_A\tgrade_B"]
    for pq_ in per_query:
        for it in pq_["items"]:
            lines.append("\t".join([
                pq_["query_id"], pq_["query"], str(it["rank"]),
                it["chunk_id"], it["document_id"], it["category"],
                f"{it['fused_score']:.6f}",
                texts.get(it["chunk_id"], ""), "", ""]))
    OUT_T.write_text("\n".join(lines) + "\n")

    print(f"[p2] WROTE {OUT_R}")
    print(f"[p2] WROTE {OUT_T} rows={len(lines) - 1}")
    print(f"[p2] retrieval artifact_sha256={body_sha}")
    print(f"[p2] wall_s={time.perf_counter() - t0:.1f}")


if __name__ == "__main__":
    main()
