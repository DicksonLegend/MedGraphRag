#!/usr/bin/env python
"""Phase 2E — compute final Phase-2 IR metrics from the two-assessor grading sheet.

INPUT : evaluations/phase2_grading_sheet.tsv AFTER human graders fill grade_A
        and grade_B columns (values exactly 1.0 / 0.4 / 0.0; blank = ungraded).
OUTPUT: evaluations/phase2_ir_metrics_final.json

Computes:
  per assessor   : P@5, R@5, MRR, nDCG@10
                   (R@5 excludes queries with zero relevant chunks for that
                    assessor — same convention as step17_ir_metrics_v2)
  agreement      : raw percent agreement + Cohen's Kappa over all commonly
                   graded rows treating grades as categorical {0.0, 0.4, 1.0}
  consensus rule : if grade_A == grade_B -> that value;
                   else ADJUDICATION REQUIRED (row flagged 'adjudicate'; the
                   final metrics below use consensus rows only until an
                   adjudicated value is written into an optional
                   'grade_final' column, which this script prefers when present)
  final IR       : computed from grade_final if present else from consensus
                   subset; queries with any unresolved conflict are EXCLUDED
                   from final metrics and listed in `excluded_conflicted_queries`.

DO NOT RUN until both grade columns are filled.
Usage: Data_Normalization/.venv/bin/python evaluations/compute_phase2_metrics.py
"""
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TSV = ROOT / "evaluations/phase2_grading_sheet.tsv"
OUT = ROOT / "evaluations/phase2_ir_metrics_final.json"
GRADES = (1.0, 0.4, 0.0)
REL = 0.4


def dcg(gains):
    return sum(g / math.log2(i + 1) for i, g in enumerate(gains, 1))


def ir_for_query(gains):
    rel_total = sum(1 for g in gains if g >= REL)
    p5 = sum(1 for g in gains[:5] if g >= REL) / min(5, len(gains)) if gains else 0.0
    r5 = (sum(1 for g in gains[:5] if g >= REL) / rel_total) if rel_total else None
    mrr = next((1.0 / i for i, g in enumerate(gains, 1) if g >= REL), 0.0)
    ideal = sorted(gains, reverse=True)[:10]
    nd = dcg(gains[:10]) / dcg(ideal) if dcg(ideal) else 0.0
    return {"P@5": round(p5, 4),
            "R@5": round(r5, 4) if r5 is not None else "EXCLUDED_zero_rel",
            "MRR": round(mrr, 4), "nDCG@10": round(nd, 4),
            "rel_total": rel_total}


def macro(per_query, key):
    vals = [m[key] for m in per_query.values()
            if not (key == "R@5" and m[key] == "EXCLUDED_zero_rel")]
    return round(sum(vals) / len(vals), 4) if vals else None


def cohens_kappa(pairs):
    """pairs: list of (a, b) categorical grades."""
    if not pairs:
        return None, None
    agree = sum(1 for a, b in pairs if a == b)
    po = agree / len(pairs)
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum((ca[c] / len(pairs)) * (cb[c] / len(pairs)) for c in GRADES)
    kappa = (po - pe) / (1 - pe) if pe < 1 else 1.0
    return round(po, 4), round(kappa, 4)


def main() -> None:
    lines = TSV.read_text().splitlines()
    header = lines[0].split("\t")
    idx = {name: header.index(name) for name in
           ("query_id", "rank", "chunk_id", "grade_A", "grade_B", "grade_final")}
    rows = [dict(zip(header, l.split("\t"))) for l in lines[1:] if l.strip()]

    # organize: query_id -> rank -> row
    by_q: dict[str, dict[int, dict]] = {}
    for r in rows:
        by_q.setdefault(r["query_id"], {})[int(r["rank"])] = r

    ungraded = [r for r in rows if not r["grade_A"] or not r["grade_B"]]
    bad_values = [r for r in rows
                  if r["grade_A"] and float(r["grade_A"]) not in GRADES
                  or r["grade_B"] and float(r["grade_B"]) not in GRADES]
    if ungraded or bad_values:
        print(f"ABORT: {len(ungraded)} ungraded rows, {len(bad_values)} invalid "
              f"values. Fill grade_A/grade_B with exactly 1.0/0.4/0.0 first.")
        sys.exit(2)

    assessors = {"A": [], "B": []}          # per-assessor per-query gains dicts
    pairs, conflicts, consensus_map = [], [], {}
    for qid, ranks in sorted(by_q.items()):
        ga, gb, fin = [], [], []
        conflicted = False
        for rank in sorted(ranks):
            r = ranks[rank]
            a, b = float(r["grade_A"]), float(r["grade_B"])
            ga.append(a)
            gb.append(b)
            pairs.append((a, b))
            if r.get("grade_final"):
                fin.append(float(r["grade_final"]))
            elif a == b:
                fin.append(a)
            else:
                conflicts.append({"query_id": qid, "rank": rank,
                                  "chunk_id": r["chunk_id"],
                                  "grade_A": a, "grade_B": b})
                conflicted = True
        if conflicted and not any(r.get("grade_final") for rr in [ranks[rk] for rk in sorted(ranks)]):
            pass
        assessors["A"][qid] = ir_for_query(ga)
        assessors["B"][qid] = ir_for_query(gb)
        consensus_map[qid] = {"gains": fin, "conflicted_no_adjudication": conflicted}

    summary = {}
    for who in ("A", "B"):
        per_q = assessors[who]
        summary[f"assessor_{who}"] = {
            "P@5": macro(per_q, "P@5"),
            "R@5": macro(per_q, "R@5"),
            "MRR": macro(per_q, "MRR"),
            "nDCG@10": macro(per_q, "nDCG@10"),
            "per_query": per_q,
        }
    po, kappa = cohens_kappa(pairs)
    summary["agreement"] = {"rows_compared": len(pairs),
                            "raw_percent_agreement": po,
                            "cohens_kappa": kappa,
                            "interpretation": (
                                "almost perfect" if kappa is not None and kappa >= 0.81 else
                                "substantial" if kappa is not None and kappa >= 0.61 else
                                "moderate" if kappa is not None and kappa >= 0.41 else
                                "fair" if kappa is not None and kappa >= 0.21 else
                                "slight/poor")}

    # Final metrics: prefer grade_final column; drop conflicted-without-adjudication
    final_rows = {}
    excluded = []
    for qid, info in consensus_map.items():
        if info["conflicted_no_adjudication"]:
            excluded.append(qid)
            continue
        final_rows[qid] = ir_for_query(info["gains"])
    final = {k: macro(final_rows, k) for k in ("P@5", "R@5", "MRR", "nDCG@10")}
    final["n_queries_used"] = len(final_rows)
    final["excluded_conflicted_queries"] = excluded

    payload = {
        "stage": "PHASE2_ir_metrics_final",
        "qrel_policy": "two human assessors, rubric evaluations/phase2_relevance_rubric.md; "
                       "grades categorical 1.0/0.4/0.0; consensus=agree rows or "
                       "explicit grade_final overrides",
        "summary": summary,
        "final_metrics": final,
        "conflicts_requiring_adjudication": conflicts,
        "timestamp": __import__("time").strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    OUT.write_text(json.dumps(payload, indent=2))
    print(json.dumps({"agreement": summary["agreement"],
                      "assessor_A": {k: v for k, v in summary["assessor_A"].items()
                                     if k != "per_query"},
                      "assessor_B": {k: v for k, v in summary["assessor_B"].items()
                                     if k != "per_query"},
                      "final_metrics": final}, indent=2))


if __name__ == "__main__":
    main()
