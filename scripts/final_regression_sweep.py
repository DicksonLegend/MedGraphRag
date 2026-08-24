#!/usr/bin/env python
"""Final Journal-Phase Regression Sweep — P01–P05 through HybridRetrievalService.

Reuses scripts/j1/run_regression.py::run_regression_suite (identical retrieval
code path) and hashes the result with scripts/j1/verify_drift.py's
latency-stripped retrieval signature. Golden hash: ba1b5121…eac.
Output: evaluations/regression_final.json (artifact_sha256 = sha256 of the
serialized payload EXCLUDING the self-referential field; j1 convention).
"""
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "j1"))
import run_regression as j1reg  # noqa: E402

EXPECTED_HASH = "ba1b512168fc4a949d12b0547e6992c4dddae63ca30b2294b13e47c9c0d18eac"
EXPECTED_TOP = {
    "P01": 0.177352,
    "P02": 0.1842,
    "P03": 0.176129,
    "P04": 0.17694,
    "P05": 0.0172,
}
TOL = 5e-6
OUT = ROOT / "evaluations/regression_final.json"
TMP = ROOT / "evaluations/scratch/_final_regression_tmp.json"


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


def main() -> None:
    t0 = time.perf_counter()
    payload = j1reg.run_regression_suite(TMP)
    actual_hash = hashlib.sha256(
        json.dumps(retrieval_signature(payload), indent=2, sort_keys=True)
        .encode("utf-8")).hexdigest()
    hash_ok = actual_hash == EXPECTED_HASH

    scores = {q["id"]: q["top_fused_score"] for q in payload["results"]}
    queries = []
    for pid in ["P01", "P02", "P03", "P04", "P05"]:
        s = scores[pid]
        score_ok = abs(s - EXPECTED_TOP[pid]) <= TOL
        queries.append({"id": pid, "query": next(q["query"] for q in payload["results"]
                                                 if q["id"] == pid),
                        "top_fused_score": s,
                        "status": "PASS" if score_ok else "FAIL"})
    verdict = ("0.00% DRIFT (100% BYTE-IDENTICAL RETRIEVAL)" if hash_ok
               else "DRIFT DETECTED")

    doc = {
        "suite": "Final Journal-Phase Regression Sweep",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "expected_hash": EXPECTED_HASH,
        "actual_hash": actual_hash,
        "queries": queries,
        "overall_verdict": verdict,
    }
    body = json.dumps(doc, indent=2).encode("utf-8")
    doc["artifact_sha256"] = hashlib.sha256(body).hexdigest()
    OUT.write_text(json.dumps(doc, indent=2))
    TMP.unlink(missing_ok=True)

    print(f"[sweep] execution_time_s={time.perf_counter() - t0:.1f}")
    print(f"[sweep] actual_hash={actual_hash}")
    print(f"[sweep] expected     ={EXPECTED_HASH}")
    for q in queries:
        exp = EXPECTED_TOP[q['id']]
        print(f"[sweep] {q['id']}: top_fused={q['top_fused_score']} "
              f"(expected {exp}) -> {q['status']}")
    print(f"[sweep] VERDICT: {verdict}")
    print(f"[sweep] artifact_sha256={doc['artifact_sha256']} (body-without-field convention)")
    sys.exit(0 if hash_ok else 1)


if __name__ == "__main__":
    main()
