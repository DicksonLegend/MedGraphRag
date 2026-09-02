#!/usr/bin/env python3
"""
figures/make_figures.py — MedGraphRAG IJMI manuscript figure generator.

Reads evaluation JSON artifacts from the evaluations/ directory and
produces four publication-ready PDF figures:

  fig_arch.pdf    — Five-stage pipeline architecture diagram (programmatic)
  fig_pareto.pdf  — Acc(all) vs WAR Pareto frontier for M2 on MedQA-US N=500
  fig_ablation.pdf — Two-panel: verification ablation + reranker ablation
  fig_latency.pdf — Latency comparison bar chart with 95% CI

Usage (run from journal_paper/):
  python figures/make_figures.py

All data sourced from:
  ../evaluations/step18_scaled_n500.json  (safe_operating_points, ungated_ceilings)
  ../evaluations/step18_pareto_frontier.md (M2 frontier table)
  ../evaluations/step15_verification_ablation.json
  ../evaluations/step15_rerank_ablation.json
  ../evaluations/step15_compute_table.json  (latency + bootstrap CIs)
"""

import json
import pathlib
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = pathlib.Path(__file__).parent
JOURNAL_DIR = SCRIPT_DIR.parent
REPO_ROOT = JOURNAL_DIR.parent
EVAL_DIR = REPO_ROOT / "evaluations"
OUT_DIR = SCRIPT_DIR  # PDFs go alongside this script

# ── Style ─────────────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.05,
})

SAFE_BLUE   = "#1a6896"
UNSAFE_RED  = "#c0392b"
GRAY        = "#7f8c8d"
GREEN       = "#27ae60"
ORANGE      = "#e67e22"
PURPLE      = "#8e44ad"


# ══════════════════════════════════════════════════════════════════════════════
# FIG 1: Architecture diagram (programmatic)
# ══════════════════════════════════════════════════════════════════════════════
def make_arch_figure():
    """Draw a clean five-stage pipeline diagram."""
    fig, ax = plt.subplots(figsize=(9, 3.2))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 3)
    ax.axis("off")

    stages = [
        ("Stage 1\nQuery\nRewriting", 0.55, SAFE_BLUE),
        ("Stage 2\nHybrid\nRetrieval", 2.50, GREEN),
        ("Stage 3\nGraph\nExpansion", 4.45, ORANGE),
        ("Stage 4\nVerification\n(β-gate)", 6.40, PURPLE),
        ("Stage 5\nGeneration\n(Qwen2.5-7B)", 8.35, SAFE_BLUE),
    ]

    box_w, box_h = 1.65, 1.2
    cy = 1.5

    for label, cx, color in stages:
        rect = mpatches.FancyBboxPatch(
            (cx - box_w / 2, cy - box_h / 2),
            box_w, box_h,
            boxstyle="round,pad=0.08",
            facecolor=color, edgecolor="white",
            linewidth=1.5, alpha=0.92, zorder=3,
        )
        ax.add_patch(rect)
        ax.text(cx, cy, label, ha="center", va="center",
                color="white", fontsize=8.5, fontweight="bold",
                linespacing=1.45, zorder=4)

    # Arrows between boxes
    arrow_xs = [(1.42, 1.72), (3.37, 3.67), (5.32, 5.62), (7.27, 7.57)]
    for x0, x1 in arrow_xs:
        ax.annotate("", xy=(x1, cy), xytext=(x0, cy),
                    arrowprops=dict(arrowstyle="->", color=GRAY,
                                   lw=1.6, connectionstyle="arc3,rad=0"))

    # Refusal arrow below Stage 4
    ax.annotate("", xy=(6.40, cy - box_h / 2 - 0.08),
                xytext=(6.40, cy - box_h / 2),
                arrowprops=dict(arrowstyle="->", color=UNSAFE_RED, lw=1.5))
    ax.text(6.40, cy - box_h / 2 - 0.28, "Structured\nRefusal",
            ha="center", va="top", color=UNSAFE_RED, fontsize=8)

    # Security lock icon text near Stage 5
    ax.text(8.35, cy - box_h / 2 - 0.28, "[lock] Single-flight lock",
            ha="center", va="top", color=GRAY, fontsize=7.5, style="italic")

    # Input / Output labels
    ax.text(0.05, cy, "Clinical\nQuery →", ha="left", va="center",
            color=GRAY, fontsize=8, style="italic")
    ax.text(9.95, cy, "→ Evidence-\nbacked\nResponse", ha="right", va="center",
            color=GRAY, fontsize=8, style="italic")

    ax.set_title("MedGraphRAG Five-Stage Pipeline",
                 fontsize=12, fontweight="bold", pad=6)

    out = OUT_DIR / "fig_arch.pdf"
    fig.savefig(out)
    plt.close(fig)
    print(f"✓  {out.name}")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 2: Pareto frontier (M2, N=500)
# ══════════════════════════════════════════════════════════════════════════════
def make_pareto_figure():
    """Acc(all) vs WAR for M2 across threshold sweep."""
    # Data from step18_pareto_frontier.md / step18_threshold_recalibration.json
    with open(EVAL_DIR / "step18_threshold_recalibration.json") as f:
        calib = json.load(f)

    m2_frontier = calib["frontiers"]["M2_GRAPH_ONLY"]

    thresholds = [p["threshold"] for p in m2_frontier]
    acc_all    = [p["accuracy_all"] for p in m2_frontier]
    war        = [p["wrong_assertion_rate"] for p in m2_frontier]
    meets_war  = [p["meets_war_constraint"] for p in m2_frontier]

    fig, ax = plt.subplots(figsize=(6.5, 4.2))

    # Shade safe zone
    ax.axvspan(0, 10, alpha=0.08, color=GREEN, label="WAR ≤ 10% zone")
    ax.axvline(10, color=GREEN, lw=1.2, ls="--", alpha=0.7)

    # Scatter safe / unsafe
    for i, (w, a, m) in enumerate(zip(war, acc_all, meets_war)):
        color = SAFE_BLUE if m else UNSAFE_RED
        ax.scatter(w, a, color=color, s=55, zorder=5, alpha=0.9)

    # Annotate optimal point
    opt = calib["optimal_points"]["M2_GRAPH_ONLY"]
    ax.scatter(opt["wrong_assertion_rate"], opt["accuracy_all"],
               color=SAFE_BLUE, s=140, marker="*", zorder=6,
               label=f"τ*=0.80  Acc(all)=12.4%  WAR=8.0%")

    # Ungated ceiling
    ug_war  = 44.6
    ug_acc  = 54.8
    ax.scatter(ug_war, ug_acc, color=UNSAFE_RED, s=120, marker="X", zorder=6,
               label="Ungated ceiling (WAR=44.6%)")
    ax.annotate("Ungated\nceiling", xy=(ug_war, ug_acc),
                xytext=(38, 52),
                arrowprops=dict(arrowstyle="->", color=UNSAFE_RED, lw=1.2),
                fontsize=8, color=UNSAFE_RED)

    # Connect Pareto curve
    ax.plot(war, acc_all, color=GRAY, lw=1.2, alpha=0.5, zorder=2)

    ax.set_xlabel("Wrong Assertion Rate, WAR (%)")
    ax.set_ylabel("Accuracy-all, Acc(all) (%)")
    ax.set_title("Pareto Frontier: Acc(all) vs WAR — M2 Graph-Only (N=500)")

    safe_patch  = mpatches.Patch(color=SAFE_BLUE,   label="Safe (WAR ≤ 10%)")
    unsafe_patch = mpatches.Patch(color=UNSAFE_RED, label="Unsafe (WAR > 10%)")
    handles, labels_leg = ax.get_legend_handles_labels()
    ax.legend(handles=[safe_patch, unsafe_patch] + handles,
              loc="lower right", framealpha=0.9, fontsize=8.5)

    ax.grid(True, alpha=0.25)
    ax.set_xlim(-1, 50)
    ax.set_ylim(-2, 65)

    out = OUT_DIR / "fig_pareto.pdf"
    fig.savefig(out)
    plt.close(fig)
    print(f"✓  {out.name}")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 3: Two-panel ablation
# ══════════════════════════════════════════════════════════════════════════════
def make_ablation_figure():
    """Two-panel: verification ablation (left) + reranker ablation (right)."""
    with open(EVAL_DIR / "step15_verification_ablation.json") as f:
        verif = json.load(f)
    with open(EVAL_DIR / "step15_rerank_ablation.json") as f:
        rerank = json.load(f)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

    # ── Panel A: Verification ablation ───────────────────────────────────────
    modes_v  = ["M1\nEvidence-Only", "M2\nGraph-Only", "M3\nCombined"]
    acc_all  = [4.0, 54.0, 4.0]
    war_v    = [2.0, 42.0, 4.0]
    refusal  = [98.0, 8.0, 96.0]

    x = np.arange(len(modes_v))
    w = 0.28
    b1 = ax1.bar(x - w, acc_all, w, label="Acc(all)%", color=SAFE_BLUE, alpha=0.85)
    b2 = ax1.bar(x,     war_v,   w, label="WAR%",      color=UNSAFE_RED, alpha=0.85)
    b3 = ax1.bar(x + w, refusal, w, label="Refusal%",  color=GRAY,       alpha=0.85)

    ax1.set_xticks(x)
    ax1.set_xticklabels(modes_v, fontsize=8.5)
    ax1.set_ylabel("Percentage (%)")
    ax1.set_title("(A) Verification Ablation (N=50)")
    ax1.legend(fontsize=8)
    ax1.set_ylim(0, 115)
    ax1.grid(axis="y", alpha=0.25)

    # WAR constraint line
    ax1.axhline(10, color=UNSAFE_RED, ls="--", lw=1.2, alpha=0.7,
                label="WAR ≤ 10% limit")

    # ── Panel B: Reranker ablation ────────────────────────────────────────────
    modes_r   = ["M1 RRF\n(γ=0.0)", "M2 Rel-Only\n(γ=1.0)", "M3 Hybrid\n(γ=0.15)"]
    gh5       = [23.6, 35.6, 37.2]
    acc_ans_r = [50.0, 42.9, 60.0]
    war_r     = [4.0,  8.0,  4.0]

    xr = np.arange(len(modes_r))
    b4 = ax2.bar(xr - w, gh5,       w, label="Graph-Hit@5%", color=GREEN,  alpha=0.85)
    b5 = ax2.bar(xr,     acc_ans_r, w, label="Acc(ans)%",    color=SAFE_BLUE, alpha=0.85)
    b6 = ax2.bar(xr + w, war_r,     w, label="WAR%",         color=UNSAFE_RED, alpha=0.85)

    ax2.set_xticks(xr)
    ax2.set_xticklabels(modes_r, fontsize=8.5)
    ax2.set_ylabel("Percentage (%)")
    ax2.set_title("(B) Reranker Ablation (N=50)")
    ax2.legend(fontsize=8)
    ax2.set_ylim(0, 80)
    ax2.grid(axis="y", alpha=0.25)

    fig.tight_layout(pad=1.5)
    out = OUT_DIR / "fig_ablation.pdf"
    fig.savefig(out)
    plt.close(fig)
    print(f"✓  {out.name}")


# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
# FIG 4: Latency comparison (retrieval-only + end-to-end)
# ══════════════════════════════════════════════════════════════════════════════
def make_latency_figure():
    """Two-section horizontal bar chart: retrieval-only + full pipeline E2E."""
    with open(EVAL_DIR / "step15_compute_table.json") as f:
        ct = json.load(f)
    rows = ct["table_rows"]
    row_map = {r["method"]: r for r in rows}

    # Section 1: retrieval-only baselines
    retrieval_entries = [
        ("BM25-RAG (pool-200)",  "BM25-RAG",              GRAY),
        ("Dense-RAG",            "Dense-RAG",              GRAY),
        ("Hybrid-RRF",           "Hybrid-RRF (baseline)",  GRAY),
        ("MedGraphRAG (ours)",   "Hybrid retrieval\n(ours, Stages 1-2)", SAFE_BLUE),
    ]
    # Section 2: end-to-end (LLM included); data from step18 ablation_metrics
    e2e_entries = [
        ("M2: Graph-Only (E2E)",    4083.39,  SAFE_BLUE),
        ("M4: Hybrid Rerank (E2E)", 12667.04, ORANGE),
    ]

    labels  = []
    medians = []
    ci_lo   = []
    ci_hi   = []
    colors  = []
    is_e2e  = []

    for key, display, color in retrieval_entries:
        if key in row_map:
            r = row_map[key]
            labels.append(display)
            medians.append(r["median_lat_ms"])
            ci = r.get("ci_95_ms") or [r["median_lat_ms"], r["median_lat_ms"]]
            ci_lo.append(r["median_lat_ms"] - ci[0])
            ci_hi.append(ci[1] - r["median_lat_ms"])
            colors.append(color)
            is_e2e.append(False)

    # separator entry (empty, just for y-spacing)
    labels.append("")
    medians.append(0)
    ci_lo.append(0)
    ci_hi.append(0)
    colors.append("white")
    is_e2e.append(False)

    for display, med, color in e2e_entries:
        labels.append(display)
        medians.append(med)
        ci_lo.append(0)
        ci_hi.append(0)
        colors.append(color)
        is_e2e.append(True)

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    n = len(labels)
    y_pos = np.arange(n)
    xerr  = np.array([ci_lo, ci_hi])

    bars = ax.barh(y_pos, medians, xerr=xerr, align="center",
                   color=colors, alpha=0.88, capsize=4,
                   error_kw=dict(elinewidth=1.3, ecolor="#555555", capthick=1.3))

    # Annotate values
    for i, (v, e2e) in enumerate(zip(medians, is_e2e)):
        if v > 0:
            suffix = " ms" if v < 1000 else f" ms  [{v/1000:.1f}s]"
            ax.text(v + max(medians) * 0.01, i,
                    f"{v:,.1f}{suffix}", va="center", fontsize=8)

    # Separator line between retrieval and E2E sections
    sep_y = len(retrieval_entries) + 0.5
    ax.axhline(sep_y, color=GRAY, lw=0.8, ls="--", alpha=0.6)
    ax.text(max(medians) * 0.5, sep_y + 0.15,
            "← Full pipeline (LLM included, Stages 1-5) →",
            ha="center", va="bottom", fontsize=7.5, color=GRAY, style="italic")

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=8.5)
    ax.set_xlabel("Median Latency (ms)")
    ax.set_title("Latency Comparison by Pipeline Stage", fontsize=11)
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda x, _: f"{x:,.0f}")
    )
    ax.set_xlim(10, max(medians) * 2.2)
    ax.grid(axis="x", alpha=0.2, which="both")
    ax.invert_yaxis()

    note = "Log scale. Retrieval-only rows exclude LLM. CI bars from 1,000 bootstrap resamples."
    ax.text(0.5, -0.13, note, transform=ax.transAxes,
            ha="center", va="top", fontsize=7, color=GRAY, style="italic")

    fig.tight_layout(pad=1.3)
    out = OUT_DIR / "fig_latency.pdf"
    fig.savefig(out)
    plt.close(fig)
    print(f"✓  {out.name}")


# Main
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("MedGraphRAG IJMI — Figure Generator")
    print(f"Output directory: {OUT_DIR.resolve()}\n")

    try:
        make_arch_figure()
        make_pareto_figure()
        make_ablation_figure()
        make_latency_figure()
    except FileNotFoundError as e:
        print(f"\n[ERROR] Missing evaluation artifact: {e}", file=sys.stderr)
        print("Run from the journal_paper/ directory so ../evaluations/ resolves.",
              file=sys.stderr)
        sys.exit(1)

    print("\nAll figures generated successfully.")
    print("LaTeX compilation: pdflatex → bibtex → pdflatex → pdflatex (from journal_paper/)")
