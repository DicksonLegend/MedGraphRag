#!/usr/bin/env python
"""J6: IR metrics (P@5, R@5, MRR, nDCG@10) over the 10-query J8 pilot set.

QREL POLICY (ASSUMPTION, logged): no clinician qrels exist for these queries.
Relevance is graded by lexical overlap (ROUGE-L-style token F1) between each
retrieved chunk and the query + graph-corroborated answer focus terms:
  grade >= 0.5 relevant(2), >= 0.2 marginally relevant(1), else 0.
This is WEAK SUPERVISION for pipeline regression tracking only — NOT
publication-grade. Replace with adjudicated qrels for the paper.
Retrieval-only (no LLM), CPU-only, run under MemoryMax=6G cgroup.
Output: evaluations/multimodal/step17_ir_metrics.json (owned path).
"""
import hashlib
import json
import resource
import time
from collections import Counter
from pathlib import Path

import re

ROOT = Path("/home/dicksone/Documents/MedGraphRag")
OUT = ROOT / "evaluations/multimodal/step17_ir_metrics.json"
PILOT = ROOT / "evaluations/baselines/baseline_retrieval_results.json"

STOP = set("a an and are as at be by for from has have in is it its of on or that the to was were with which what who whom this these those there their".split())


def tokens(s: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", s.lower()) if t not in STOP and len(t) > 2]


def overlap_grade(query: str, chunk_text: str) -> float:
    qt, ct = Counter(tokens(query)), Counter(tokens(chunk_text))
    if not qt:
        return 0.0
    inter = sum(min(qt[t], ct.get(t, 0)) for t in qt)
    denom = min(sum(qt.values()), max(1, len(qt)))
    return inter / max(1, sum(qt.values())) if ct else 0.0


def ir_metrics(ranked_grades: list[float], k: int, total_relevant: int) -> dict:
    hits = [g for g in ranked_grades[:k]]
    p_at_k = sum(1 for g in hits if g >= 0.2) / k
    r_at_k = (sum(1 for g in hits if g >= 0.2) / total_relevant) if total_relevant else 0.0
    mrr = 0.0
    for i, g in enumerate(hits, 1):
        if g >= 0.2:
            mrr = 1.0 / i
            break
    dcg = sum((2**g - 1) / __import__("math").log2(i + 1) for i, g in enumerate(ranked_grades[:10], 1))
    ideal = sorted(ranked_grades, reverse=True)[:10]
    idcg = sum((2**g - 1) / __import__("math").log2(i + 1) for i, g in enumerate(ideal, 1))
    return {"P@5": round(p_at_k, 4), "R@5": round(r_at_k, 4),
            "MRR": round(mrr, 4), "nDCG@10": round(dcg / idcg, 4) if idcg else 0.0}


def main() -> None:
    import sys
    sys.path.insert(0, str(ROOT / "backend"))
    from app.core.retrieval.service import HybridRetrievalService
    from app.core.retrieval.schemas import RetrievalRequest

    pilot = json.loads(PILOT.read_text())
    queries = pilot["queries"]
    svc = HybridRetrievalService()

    per_query = []
    agg = {"P@5": 0.0, "R@5": 0.0, "MRR": 0.0, "nDCG@10": 0.0}
    t0 = time.perf_counter()
    for q in queries:
        res = svc.retrieve(RetrievalRequest(query=q, destination="global"))
        grades = []
        for ev in res.items:
            grades.append(1.0 if overlap_grade(q, getattr(ev, "text_snippet", "") or getattr(ev, "text", "") or "") >= 0.5
                          else (0.4 if overlap_grade(q, getattr(ev, "text_snippet", "") or getattr(ev, "text", "") or "") >= 0.2 else 0.0))
        total_rel = sum(1 for g in grades if g >= 0.2)
        m = ir_metrics(grades, 5, total_rel)
        per_query.append({"query": q, "grades": grades, **m})
        for k in agg:
            agg[k] += m[k]
    n = max(1, len(queries))
    summary = {k: round(v / n, 4) for k, v in agg.items()}
    summary["queries"] = len(queries)
    summary["peak_rss_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
    summary["wall_seconds"] = round(time.perf_counter() - t0, 2)

    payload = {
        "stage": "J6_ir_metrics",
        "qrel_policy": "PROXY lexical-overlap weak supervision (see header); not publication-grade",
        "summary": summary,
        "per_query": per_query,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2))
    payload["artifact_sha256"] = hashlib.sha256(OUT.read_bytes()).hexdigest()
    print(json.dumps({"summary": summary, "artifact_sha256": payload["artifact_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
