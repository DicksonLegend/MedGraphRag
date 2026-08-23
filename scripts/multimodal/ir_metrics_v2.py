#!/usr/bin/env python
"""STEP 5b: IR metrics v2 from user-adjudicated graded qrels (single assessor).

Gains: 1.0 / 0.4 / 0.0 in grading-sheet order (Q1..Q10, MedGraphRAG top-10).
P@5: count(gain>=0.4 in top-5)/5. R@5: count(gain>=0.4 in top-5)/total_rel
(TREC convention: queries with zero relevant docs excluded from R-avg).
MRR: 1/first rank with gain>=0.4. nDCG@10: graded gains, log2 discount.
Output: evaluations/multimodal/step17_ir_metrics_v2.json (v1 kept).
"""
import hashlib
import json
import time
from math import log2
from pathlib import Path

ROOT = Path("/home/dicksone/Documents/MedGraphRag")
OUT = ROOT / "evaluations/multimodal/step17_ir_metrics_v2.json"
BASE = ROOT / "evaluations/step17_baselines.json"

GRADES = {
    "Q1":  [0.4, 0, 0, 0, 0.4, 0, 0, 0, 0, 0],
    "Q2":  [0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0],
    "Q3":  [0, 0, 0, 0, 0.4, 0, 0, 0, 0, 0],
    "Q4":  [0, 0, 0, 0, 0, 0.4, 0, 0, 0, 0.4],
    "Q5":  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "Q6":  [0.4, 0, 0, 0.4, 0, 0.4, 0, 0, 0, 0],
    "Q7":  [0.4, 0.4, 0.4, 0, 0.4, 0, 0, 0.4, 0.4, 0.4],
    "Q8":  [0, 0, 0, 0, 0, 0, 0, 0],
    "Q9":  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "Q10": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
}
REL = 0.4


def dcg(gains):
    return sum(g / log2(i + 1) for i, g in enumerate(gains, 1))


def main() -> None:
    d = json.loads(BASE.read_text())
    queries = [q["query"] for q in d["queries"]][:10]
    per_q = {}
    ps, rrs, mrrs, ndcgs, r_qs = [], [], [], [], []
    for i, q in enumerate(queries, 1):
        g = GRADES[f"Q{i}"]
        rel_total = sum(1 for x in g if x >= REL)
        top5 = g[:5]
        p5 = sum(1 for x in top5 if x >= REL) / 5
        r5 = (sum(1 for x in top5 if x >= REL) / rel_total) if rel_total else None
        mrr = 0.0
        for r, x in enumerate(g, 1):
            if x >= REL:
                mrr = 1.0 / r
                break
        ideal = sorted(g, reverse=True)[:10]
        nd = dcg(g) / dcg(ideal) if dcg(ideal) else 0.0
        per_q[f"Q{i}"] = {"query": q[:80], "gains": g, "rel_total": rel_total,
                          "P@5": round(p5, 4),
                          "R@5": round(r5, 4) if r5 is not None else "excluded(no rel)",
                          "MRR": round(mrr, 4), "nDCG@10": round(nd, 4)}
        ps.append(p5)
        if rel_total:
            rrs.append(r5)
            r_qs.append(f"Q{i}")
        mrrs.append(mrr)
        ndcgs.append(nd)
    summary = {
        "P@5": round(sum(ps) / len(ps), 4),
        "R@5": round(sum(rrs) / len(rrs), 4),
        "R@5_queries_used": r_qs,
        "MRR": round(sum(mrrs) / len(mrrs), 4),
        "nDCG@10": round(sum(ndcgs) / len(ndcgs), 4),
        "N_queries": 10,
    }
    payload = {
        "stage": "J6_ir_metrics_v2",
        "qrel_policy": "user-adjudicated graded qrels (single assessor); gains 1.0/0.4/0.0",
        "summary": summary,
        "per_query": per_q,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    OUT.write_text(json.dumps(payload, indent=2))
    payload["artifact_sha256"] = hashlib.sha256(OUT.read_bytes()).hexdigest()
    print(json.dumps({"summary": summary,
                      "artifact_sha256": payload["artifact_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
