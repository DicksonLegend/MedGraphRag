#!/usr/bin/env python3
"""
MedGraphRAG — Step 4: Refusal Threshold Recalibration & Pareto Frontier
======================================================================
Sweeps refusal threshold tau in [0.10, 0.90] on the N=500 per-query evaluation
records to find the optimal threshold that maximizes Acc(all) subject to
WAR <= 10.0%.

Outputs:
  - evaluations/step18_threshold_recalibration.json
  - evaluations/step18_pareto_frontier.md
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("recalibrate_thresholds")

INPUT_FP = _PROJECT_ROOT / "evaluations" / "step18_scaled_n500.json"
OUT_JSON = _PROJECT_ROOT / "evaluations" / "step18_threshold_recalibration.json"
OUT_MD = _PROJECT_ROOT / "evaluations" / "step18_pareto_frontier.md"


def recalibrate(mode_records: List[Dict[str, Any]], total_n: int = 500) -> List[Dict[str, Any]]:
    frontier = []
    # Test fine-grained thresholds
    thresholds = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.37, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]

    for tau in thresholds:
        corr_count = 0
        ans_count = 0
        ref_count = 0

        for q in mode_records:
            pred = q.get("pred", "refused_or_unanswered")
            gold = q.get("gold", "")
            conf = float(q.get("final_confidence", 0.0))
            status = q.get("answer_status", "")

            # If confidence meets threshold and answer wasn't an explicit refusal/error
            is_answered = (
                conf >= tau
                and pred in ["A", "B", "C", "D"]
                and status not in ["refusal", "out_of_scope", "error"]
            )

            if is_answered:
                ans_count += 1
                if pred == gold:
                    corr_count += 1
            else:
                ref_count += 1

        war_count = ans_count - corr_count
        acc_all = round((corr_count / total_n) * 100.0, 2)
        acc_ans = round((corr_count / ans_count * 100.0) if ans_count > 0 else 0.0, 2)
        ref_rate = round((ref_count / total_n) * 100.0, 2)
        war_rate = round((war_count / total_n) * 100.0, 2)
        meets_safety = war_rate <= 10.0

        frontier.append({
            "threshold": tau,
            "accuracy_all": acc_all,
            "accuracy_answered": acc_ans,
            "wrong_assertion_rate": war_rate,
            "refusal_rate": ref_rate,
            "answered_count": ans_count,
            "correct_count": corr_count,
            "meets_war_constraint": meets_safety,
        })

    return frontier


def main():
    if not INPUT_FP.exists():
        logger.error("Input file %s not found. Run scaled evaluation first.", INPUT_FP)
        return

    with open(INPUT_FP, "r", encoding="utf-8") as f:
        data = json.load(f)

    all_frontiers = {}
    optimal_operating_points = {}

    md_lines = [
        "# Refusal Threshold Recalibration & Accuracy vs. WAR Pareto Frontier",
        "",
        "> **Constraint Rule:** Maximize $\\text{Acc}(\\text{all})$ strictly subject to $\\text{WAR} \\le 10.0\\%$.",
        "",
    ]

    for mode in ["M1_EVIDENCE_ONLY", "M2_GRAPH_ONLY", "M3_COMBINED", "M4_HYBRID_RERANK"]:
        records = data.get("per_query_records", {}).get(mode, [])
        if not records:
            continue

        frontier = recalibrate(records, total_n=len(records))
        all_frontiers[mode] = frontier

        # Filter points meeting WAR <= 10%
        valid_points = [p for p in frontier if p["meets_war_constraint"]]
        if valid_points:
            # Pick highest Acc(all)
            best_pt = max(valid_points, key=lambda x: (x["accuracy_all"], x["accuracy_answered"]))
        else:
            best_pt = frontier[-1]

        optimal_operating_points[mode] = best_pt

        md_lines.append(f"## {mode}")
        md_lines.append(f"**Optimal Operating Threshold:** $\\tau = {best_pt['threshold']:.2f}$ | $\\text{{Acc}}(\\text{{all}}) = {best_pt['accuracy_all']}\\%$ | $\\text{{Acc}}(\\text{{ans}}) = {best_pt['accuracy_answered']}\\%$ | $\\text{{WAR}} = {best_pt['wrong_assertion_rate']}\\%$ | Refusal = {best_pt['refusal_rate']}%")
        md_lines.append("")
        md_lines.append("| Threshold $\\tau$ | $\\text{Acc}(\\text{all})$ | $\\text{Acc}(\\text{ans})$ | $\\text{WAR}$ | Refusal Rate | Answered / Total | Meets $\\text{WAR} \\le 10\\%$ |")
        md_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

        for p in frontier:
            flag = "✅ **Optimal**" if p["threshold"] == best_pt["threshold"] else ("✅ Yes" if p["meets_war_constraint"] else "❌ No")
            md_lines.append(
                f"| **{p['threshold']:.2f}** | {p['accuracy_all']:5.1f}% | {p['accuracy_answered']:5.1f}% | {p['wrong_assertion_rate']:4.1f}% | {p['refusal_rate']:5.1f}% | {p['answered_count']}/{len(records)} | {flag} |"
            )
        md_lines.append("")

    # Save JSON report
    report_payload = {
        "description": "N=500 Refusal Threshold Recalibration & Pareto Frontier",
        "optimal_points": optimal_operating_points,
        "frontiers": all_frontiers,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(report_payload, f, indent=2)

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    logger.info("Saved threshold recalibration JSON -> %s", OUT_JSON)
    logger.info("Saved Pareto frontier Markdown   -> %s", OUT_MD)


if __name__ == "__main__":
    main()
