#!/usr/bin/env python3
"""
figures/make_figures.py — MedGraphRAG IJMI manuscript figure generator.

Reads evaluation JSON artifacts from the evaluations/ directory and
produces publication-ready PDF figures:

  fig_arch.pdf     — Five-stage pipeline architecture diagram (programmatic)
  fig_pareto.pdf   — Acc(all) vs WAR Pareto frontier across 4 modes with M2 inset
  fig_ablation.pdf — Three-panel: verification ablation + reranker ablation + rewriting
  fig_latency.pdf  — Latency comparison bar chart with 95% CI

Usage (run from repo root or journal_paper/):
  python journal_paper/figures/make_figures.py
"""

import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import FuncFormatter
import numpy as np

# Set publication style contract
matplotlib.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "axes.edgecolor": "#333333",
    "axes.linewidth": 0.8,
    "xtick.color": "#333333",
    "ytick.color": "#333333",
    "text.color": "#222222",
    "axes.labelcolor": "#222222",
})

# Curated Okabe-Ito Color Palette
OKABE_ITO = {
    "black": "#000000",
    "orange": "#E69F00",        # M2 / Secondary
    "sky_blue": "#56B4E9",
    "bluish_green": "#009E73",   # M3 / Accent
    "yellow": "#F0E442",
    "blue": "#0072B2",          # M1 / Primary
    "vermilion": "#D55E00",     # M4 / Highlight
    "reddish_purple": "#CC79A7",
    "grey": "#777777",
    "safe_green": "#E5F5E0",
}

SAFE_BLUE   = "#1a6896"
UNSAFE_RED  = "#c0392b"
GRAY        = "#7f8c8d"
GREEN       = "#27ae60"
ORANGE      = "#e67e22"
PURPLE      = "#8e44ad"

MODE_CONFIG = {
    "M1_EVIDENCE_ONLY": {
        "label": r"M1: Evidence-Only ($\beta=1.0$)",
        "color": OKABE_ITO["blue"],
        "marker": "o",
        "name": "M1",
    },
    "M2_GRAPH_ONLY": {
        "label": r"M2: Graph-Only ($\beta=0.0$)",
        "color": OKABE_ITO["orange"],
        "marker": "s",
        "name": "M2",
    },
    "M3_COMBINED": {
        "label": r"M3: Combined ($\beta=0.7$)",
        "color": OKABE_ITO["bluish_green"],
        "marker": "^",
        "name": "M3",
    },
    "M4_HYBRID_RERANK": {
        "label": r"M4: Hybrid Rerank ($\beta=0.7, \gamma=0.15$)",
        "color": OKABE_ITO["vermilion"],
        "marker": "D",
        "name": "M4",
    },
}

SCRIPT_DIR = Path(__file__).resolve().parent
JOURNAL_DIR = SCRIPT_DIR.parent
REPO_ROOT = JOURNAL_DIR.parent

if (REPO_ROOT / "evaluations").exists():
    EVAL_DIR = REPO_ROOT / "evaluations"
elif (JOURNAL_DIR / "evaluations").exists():
    EVAL_DIR = JOURNAL_DIR / "evaluations"
elif Path("evaluations").exists():
    EVAL_DIR = Path("evaluations").resolve()
else:
    EVAL_DIR = Path("../evaluations").resolve()

OUT_DIR = SCRIPT_DIR


def load_data():
    with open(EVAL_DIR / "step18_threshold_recalibration.json") as f:
        calib = json.load(f)
    with open(EVAL_DIR / "step18_scaled_n500.json") as f:
        s500 = json.load(f)
    with open(EVAL_DIR / "step15_verification_ablation.json") as f:
        v_abl = json.load(f)
    with open(EVAL_DIR / "step15_rerank_ablation.json") as f:
        r_abl = json.load(f)
    with open(EVAL_DIR / "step15_compute_table.json") as f:
        comp = json.load(f)
    return calib, s500, v_abl, r_abl, comp


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
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"✓  {out.name}")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 2: Pareto frontier (fig_pareto.pdf)
# ══════════════════════════════════════════════════════════════════════════════
def make_pareto_figure(calib, s500):
    """Acc(all) vs WAR Pareto frontier across 4 modes with M2 inset in empty region."""
    fig, ax = plt.subplots(figsize=(7.2, 3.4))

    # Shaded clinical safety zone (WAR <= 10%)
    ax.axvspan(0, 10, color=OKABE_ITO["safe_green"], alpha=0.7, zorder=1)
    ax.axvline(10, color=OKABE_ITO["bluish_green"], linestyle="--", linewidth=1.1, alpha=0.9, zorder=2)
    ax.text(5.0, 62.5, "Clinical Safety Zone\n(WAR ≤ 10%)", ha="center", va="top",
            fontsize=8.0, fontweight="bold", color="#005A36", zorder=3)

    # 4 Pareto Curves
    for mkey, cfg in MODE_CONFIG.items():
        sorted_pts = sorted(calib["frontiers"][mkey], key=lambda p: p["wrong_assertion_rate"])
        wars = [p["wrong_assertion_rate"] for p in sorted_pts]
        accs = [p["accuracy_all"] for p in sorted_pts]
        ax.plot(wars, accs, color=cfg["color"], linewidth=1.3, alpha=0.85, zorder=3)
        ax.scatter(wars, accs, color=cfg["color"], marker=cfg["marker"], s=28,
                   edgecolors="white", linewidths=0.5, zorder=4, label=cfg["label"])

    sop = s500["safe_operating_points"]
    ug = s500["ungated_ceilings"]

    for mkey, cfg in MODE_CONFIG.items():
        p_star = sop[mkey]
        ax.scatter(p_star["wrong_assertion_rate"], p_star["accuracy_all"],
                   marker="*", s=140, color=cfg["color"], edgecolors="#222222", linewidths=0.8, zorder=7)
        p_ug = ug[mkey]
        ax.scatter(p_ug["wrong_assertion_rate"], p_ug["accuracy_all"],
                   marker="X", s=85, color=cfg["color"], edgecolors="#222222", linewidths=0.8, zorder=7)

    # 1. M2 label alone: isolated with clean leader pointing to (8.0, 12.4)
    ax.annotate(r"$\mathbf{M2:\;\tau^*=0.80}$", xy=(8.0, 12.4), xytext=(4.0, 19.5),
                arrowprops=dict(arrowstyle="->", color=MODE_CONFIG["M2_GRAPH_ONLY"]["color"], lw=0.85, shrinkA=2, shrinkB=4),
                fontsize=7.2, color=MODE_CONFIG["M2_GRAPH_ONLY"]["color"], ha="center", va="center", zorder=8)

    # 2. M1/M3/M4 as one stacked offset annotation block with thin non-crossing leaders
    box_x = 12.8
    box_y = 4.2
    box_w = 6.6
    box_h = 6.4

    items = [
        ("M4_HYBRID_RERANK", (9.4, 10.0), 9.6, r"$\mathbf{M4:\;\tau^*=0.46}$"),
        ("M3_COMBINED",      (9.0, 9.8),  7.4, r"$\mathbf{M3:\;\tau^*=0.47}$"),
        ("M1_EVIDENCE_ONLY", (9.4, 9.6),  5.2, r"$\mathbf{M1:\;\tau^*=0.43}$"),
    ]

    bbox = mpatches.FancyBboxPatch((box_x, box_y), box_w, box_h, boxstyle="round,pad=0.25",
                                  facecolor="#FFFFFF", edgecolor="#B0BEC5", linewidth=0.7, alpha=0.96, zorder=7)
    ax.add_patch(bbox)

    for mkey, star_xy, y_text, txt in items:
        col = MODE_CONFIG[mkey]["color"]
        ax.annotate("", xy=star_xy, xytext=(box_x, y_text),
                    arrowprops=dict(arrowstyle="->", color=col, lw=0.75, shrinkA=0, shrinkB=4),
                    zorder=8)
        ax.text(box_x + 0.45, y_text, txt, fontsize=7.2, color=col, ha="left", va="center", zorder=9)

    # Ungated ceiling label
    ax.text(44.0, 62.5, "Ungated ceilings\n(WAR ≈ 43–45%)",
            ha="center", va="top", fontsize=7.2, color="#222222", zorder=8)

    # Trajectory arrow
    ax.annotate("Gating moves operating\npoint into safe zone",
                xy=(35.0, 40.0), xytext=(39.0, 31.0),
                arrowprops=dict(arrowstyle="->", color="#333333", lw=1.1,
                                connectionstyle="arc3,rad=0.12"),
                fontsize=7.2, color="#222222", ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.35", facecolor="#FFFFFF", edgecolor="#B0BEC5", linewidth=0.8),
                zorder=8)

    # Inset axes placed in empty region: x in [24, 38] WAR, y in [7, 24] Acc(all)
    ax_ins = ax.inset_axes([0.47, 0.10, 0.27, 0.23])
    ax_ins.patch.set_facecolor("#FFFFFF")
    ax_ins.patch.set_alpha(0.96)

    m2_pts = sorted(calib["frontiers"]["M2_GRAPH_ONLY"], key=lambda p: p["threshold"])
    m2_taus = [p["threshold"] for p in m2_pts]
    m2_ans  = [p["accuracy_answered"] for p in m2_pts]

    ax_ins.axvspan(0.77, 0.83, color=OKABE_ITO["safe_green"], alpha=0.8, zorder=1)
    ax_ins.axvline(0.77, color=OKABE_ITO["bluish_green"], linestyle="--", linewidth=0.8, alpha=0.9, zorder=2)
    ax_ins.text(0.775, 54.8, "Safe", fontsize=6.2, color="#005A36", fontweight="bold", zorder=3)

    ax_ins.plot(m2_taus, m2_ans, color=OKABE_ITO["orange"], linewidth=1.2, zorder=3)
    ax_ins.scatter(m2_taus, m2_ans, color=OKABE_ITO["orange"], marker="s", s=14,
                   edgecolors="white", linewidths=0.4, zorder=4)

    ax_ins.scatter(0.80, 60.78, marker="*", s=80, color=OKABE_ITO["orange"],
                   edgecolors="#222222", linewidths=0.7, zorder=6)
    ax_ins.annotate(r"$\tau^*=0.80$" + "\n(60.8%)", xy=(0.80, 60.78), xytext=(0.58, 61.2),
                    arrowprops=dict(arrowstyle="->", color=OKABE_ITO["orange"], lw=0.7),
                    fontsize=6.5, color=OKABE_ITO["orange"], ha="right", va="center", zorder=7)

    ax_ins.set_xlim(0.08, 0.84)
    ax_ins.set_ylim(53.5, 63.0)
    ax_ins.set_title(r"$\mathbf{M2\;Answered\;Precision\;vs.\;\tau}$", fontsize=6.8, pad=3)
    ax_ins.set_xlabel(r"Refusal Threshold $\tau$", fontsize=6.2, labelpad=1)
    ylabel = ax_ins.set_ylabel("Acc(ans) (%)", fontsize=6.2, labelpad=1)
    ylabel.set_clip_on(False)
    ax_ins.tick_params(axis="both", labelsize=5.8, pad=1)
    ax_ins.spines["top"].set_visible(False)
    ax_ins.spines["right"].set_visible(False)
    ax_ins.grid(axis="y", color="#D0D0D0", linestyle=":", linewidth=0.5, alpha=0.6)

    # Main axis formatting
    ax.set_xlim(0, 50)
    ax.set_ylim(0, 66)
    ax.set_xlabel("Wrong Assertion Rate, WAR (%)", fontsize=9.0)
    ax.set_ylabel("Overall Accuracy, Acc(all) (%)", fontsize=9.0)
    ax.tick_params(axis="both", labelsize=8.0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#CCCCCC", linestyle=":", linewidth=0.6, alpha=0.6)

    # Legend in open upper-left region
    handles, labels = ax.get_legend_handles_labels()
    star_proxy = plt.Line2D([0], [0], marker="*", color="w", markerfacecolor="#444444",
                            markeredgecolor="#222222", markersize=9, label=r"Safe operating point ($\tau^*$)")
    cross_proxy = plt.Line2D([0], [0], marker="X", color="w", markerfacecolor="#444444",
                             markeredgecolor="#222222", markersize=7, label="Ungated ceiling")
    ax.legend(handles=handles + [star_proxy, cross_proxy], loc="upper left",
              bbox_to_anchor=(0.21, 0.98), fontsize=7.0, framealpha=0.96,
              edgecolor="#CCCCCC", labelspacing=0.3)

    out = OUT_DIR / "fig_pareto.pdf"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"✓  {out.name}")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 3: Three-panel ablation (fig_ablation.pdf)
# ══════════════════════════════════════════════════════════════════════════════
def make_ablation_figure(v_abl, r_abl, s500):
    """Three-panel: verification ablation + reranker ablation + rewriting coverage."""
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(7.2, 3.0), gridspec_kw={"wspace": 0.32})

    # ── PANEL A: Verification Ablation (N=50) ──
    v_m = v_abl["ablation_metrics"]
    v_labels = ["Evidence", "Graph", "Combined*"]
    x_a = np.arange(3)
    w_a = 0.36

    acc_a = [v_m["M1_EVIDENCE_ONLY"]["accuracy_answered"],
             v_m["M2_GRAPH_ONLY"]["accuracy_answered"],
             v_m["M3_COMBINED_HYBRID"]["accuracy_answered"]]
    war_a = [v_m["M1_EVIDENCE_ONLY"]["wrong_assertion_rate"],
             v_m["M2_GRAPH_ONLY"]["wrong_assertion_rate"],
             v_m["M3_COMBINED_HYBRID"]["wrong_assertion_rate"]]

    b1_a = ax1.bar(x_a - w_a/2, acc_a, w_a, label="Acc(ans) %", color=OKABE_ITO["blue"],
                   edgecolor="#222222", linewidth=0.5, alpha=0.9, zorder=3)
    b2_a = ax1.bar(x_a + w_a/2, war_a, w_a, label="WAR %", color=OKABE_ITO["orange"],
                   edgecolor="#222222", linewidth=0.5, alpha=0.9, zorder=3)

    ax1.axhline(10, color=OKABE_ITO["bluish_green"], linestyle="--", linewidth=1.0, zorder=4)
    ax1.text(2.45, 10.8, "WAR ≤ 10%", color="#005A36", fontsize=6.8, fontweight="bold", ha="right")

    for bar in b1_a:
        h = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, h + 1.2, f"{h:.1f}%",
                 ha="center", va="bottom", fontsize=7.2)
    for bar in b2_a:
        h = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, h + 1.2, f"{h:.1f}%",
                 ha="center", va="bottom", fontsize=7.2)

    ax1.set_xticks(x_a)
    ax1.set_xticklabels(v_labels, fontsize=7.8)
    ax1.set_ylim(0, 82)
    ax1.set_ylabel("Rate (%)", fontsize=8.5)
    ax1.set_title(r"$\mathbf{(A)\;Verification\;(N=50)}$", fontsize=9.0, pad=6)
    ax1.legend(loc="upper right", fontsize=6.8, framealpha=0.9, labelspacing=0.2)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.grid(axis="y", color="#CCCCCC", linestyle=":", linewidth=0.5, alpha=0.6)

    # ── PANEL B: Reranker Bonus Ablation (N=50) ──
    r_m = r_abl["ablation_metrics"]
    modes_b = [r"$\gamma=0.0$" + "\n(RRF)", r"$\gamma=0.15$" + "\n(Hybrid)*", r"$\gamma=1.0$" + "\n(Rel-Only)"]
    x_b = np.arange(3)
    w_b = 0.36

    hit_b = [r_m["M1_RRF_CONTROL"]["graph_hit_rate_top5_pct"],
             r_m["M3_HYBRID_RERANK"]["graph_hit_rate_top5_pct"],
             r_m["M2_REL_ONLY"]["graph_hit_rate_top5_pct"]]
    acc_b = [r_m["M1_RRF_CONTROL"]["accuracy_answered"],
             r_m["M3_HYBRID_RERANK"]["accuracy_answered"],
             r_m["M2_REL_ONLY"]["accuracy_answered"]]

    b_hit = ax2.bar(x_b - w_b/2, hit_b, w_b, label="Hit@5 %", color=OKABE_ITO["bluish_green"],
                    edgecolor="#222222", linewidth=0.5, alpha=0.9, zorder=3)
    b_ac  = ax2.bar(x_b + w_b/2, acc_b, w_b, label="Acc(ans) %", color=OKABE_ITO["vermilion"],
                    edgecolor="#222222", linewidth=0.5, alpha=0.9, zorder=3)

    # Highlight optimal gamma = 0.15
    b_hit[1].set_linewidth(1.6)
    b_ac[1].set_linewidth(1.6)

    for bar in b_hit:
        h = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, h + 1.2, f"{h:.1f}%",
                 ha="center", va="bottom", fontsize=7.2)
    for bar in b_ac:
        h = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, h + 1.2, f"{h:.1f}%",
                 ha="center", va="bottom", fontsize=7.2)

    ax2.set_xticks(x_b)
    ax2.set_xticklabels(modes_b, fontsize=7.2)
    ax2.set_ylim(0, 78)
    ax2.set_ylabel("Rate (%)", fontsize=8.5)
    ax2.set_title(r"$\mathbf{(B)\;Reranker\;(N=50)}$", fontsize=9.0, pad=6)
    ax2.legend(loc="upper left", fontsize=6.8, framealpha=0.9, labelspacing=0.2)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.grid(axis="y", color="#CCCCCC", linestyle=":", linewidth=0.5, alpha=0.6)

    # ── PANEL C: Rewriting Coverage Gain (tau=0.50, N=500) ──
    c_modes = ["M1_EVIDENCE_ONLY", "M3_COMBINED", "M4_HYBRID_RERANK"]
    rew = {m: s500["matched_tau_comparison"][m]["tau_0.50"] for m in c_modes}
    c_labels = ["M1", "M3", "M4"]
    x_c = np.arange(len(c_modes))
    w_c = 0.36

    unrew_acc = [rew[m]["unrewritten"]["accuracy_all"] for m in c_modes]
    rew_acc   = [rew[m]["rewritten"]["accuracy_all"] for m in c_modes]
    deltas    = [rew[m]["delta_accuracy_all"] for m in c_modes]

    b_unrew = ax3.bar(x_c - w_c/2, unrew_acc, w_c, label="Unrewritten", color="#999999",
                      edgecolor="#222222", linewidth=0.5, alpha=0.9, zorder=3)
    b_rew   = ax3.bar(x_c + w_c/2, rew_acc, w_c, label="Rewritten", color=OKABE_ITO["blue"],
                      edgecolor="#222222", linewidth=0.5, alpha=0.9, zorder=3)

    for bar in b_unrew:
        h = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2, h + 0.25, f"{h:.1f}",
                 ha="center", va="bottom", fontsize=7.2)
    for bar in b_rew:
        h = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2, h + 0.25, f"{h:.1f}",
                 ha="center", va="bottom", fontsize=7.2)

    bracket_ys = [9.7, 10.1, 10.7]
    for i in range(len(c_modes)):
        x1 = x_c[i] - w_c/2
        x2 = x_c[i] + w_c/2
        yb = bracket_ys[i]
        ax3.plot([x1, x1, x2, x2], [yb - 0.25, yb, yb, yb - 0.25], color="#222222", lw=0.8)
        ax3.text((x1 + x2)/2, yb + 0.35, f"+{deltas[i]:.1f} pp", ha="center", va="bottom",
                 fontsize=7.2, fontweight="bold", color="#B71C1C")

    ax3.set_xticks(x_c)
    ax3.set_xticklabels(c_labels, fontsize=7.5)
    ax3.set_ylim(0, 15.0)
    ax3.set_ylabel("Acc(all) (%)", fontsize=8.5)
    ax3.set_title(r"$\mathbf{(C)\;Rewriting\;(\tau=0.50)}$", fontsize=9.0, pad=6)
    ax3.legend(loc="upper left", fontsize=6.8, framealpha=0.9, labelspacing=0.2)
    ax3.spines["top"].set_visible(False)
    ax3.spines["right"].set_visible(False)
    ax3.grid(axis="y", color="#CCCCCC", linestyle=":", linewidth=0.5, alpha=0.6)

    out = OUT_DIR / "fig_ablation.pdf"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"✓  {out.name}")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 4: Latency breakdown (fig_latency.pdf)
# ══════════════════════════════════════════════════════════════════════════════
def make_latency_figure(comp):
    """Latency comparison bar chart with 95% CI and deployment card."""
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    ct_rows = {r["method"]: r for r in comp["table_rows"]}

    entries = [
        ("Dense-RAG", "retrieval", 6.0,
         ct_rows["Dense-RAG"]["median_lat_ms"],
         ct_rows["Dense-RAG"]["ci_95_ms"],
         OKABE_ITO["grey"], None),
        ("BM25-RAG", "retrieval", 5.2,
         ct_rows["BM25-RAG (pool-200)"]["median_lat_ms"],
         ct_rows["BM25-RAG (pool-200)"]["ci_95_ms"],
         OKABE_ITO["grey"], None),
        ("Hybrid-RRF", "retrieval", 4.4,
         ct_rows["Hybrid-RRF"]["median_lat_ms"],
         ct_rows["Hybrid-RRF"]["ci_95_ms"],
         OKABE_ITO["grey"], None),
        ("Hybrid Retrieval (Ours, Stages 1–2)", "retrieval", 3.6,
         ct_rows["MedGraphRAG (ours)"]["median_lat_ms"],
         ct_rows["MedGraphRAG (ours)"]["ci_95_ms"],
         OKABE_ITO["blue"], None),

        ("M2: Graph-Only (E2E)", "e2e", 2.0,
         ct_rows["M2: Graph-Only Verification (beta=0.0)"]["median_lat_ms"],
         None,
         OKABE_ITO["orange"], "14.7 q/min"),
        ("M3: Combined (E2E)", "e2e", 1.2,
         ct_rows["M3: Combined Verification (beta=0.7)"]["median_lat_ms"],
         None,
         OKABE_ITO["bluish_green"], None),
        ("M4: Hybrid Rerank (E2E)", "e2e", 0.4,
         ct_rows["M4: Hybrid Reranker + Combined Verification (beta=0.7, gamma=0.15)"]["median_lat_ms"],
         None,
         OKABE_ITO["vermilion"], "4.7 q/min"),
    ]

    y_positions = [e[2] for e in entries]

    for label, cat, y, med, ci, color, tp in entries:
        if ci is not None:
            xerr = np.array([[med - ci[0]], [ci[1] - med]])
            ax.barh(y, med, xerr=xerr, height=0.55, align="center", color=color,
                    alpha=0.88, edgecolor="#222222", linewidth=0.5, capsize=3.5,
                    error_kw=dict(elinewidth=1.1, ecolor="#222222", capthick=1.1), zorder=3)
        else:
            ax.barh(y, med, height=0.55, align="center", color=color,
                    alpha=0.88, edgecolor="#222222", linewidth=0.5, zorder=3)

        if cat == "retrieval":
            if ci is not None and (ci[1] - ci[0] > 10):
                text_str = f"{med:.1f} ms  [95% CI: {ci[0]:.1f}–{ci[1]:.1f}]"
            else:
                text_str = f"{med:.1f} ms"
            ref_x = ci[1] if ci is not None else med
            ax.annotate(text_str, xy=(ref_x, y), xytext=(6, 0),
                        textcoords="offset points", va="center", ha="left",
                        fontsize=7.2, color="#222222")
        else:
            if tp is not None:
                text_str = f"{int(round(med)):,} ms  ({tp})"
            else:
                text_str = f"{int(round(med)):,} ms"
            ax.annotate(text_str, xy=(med, y), xytext=(6, 0),
                        textcoords="offset points", va="center", ha="left",
                        fontsize=7.2, color="#222222")

    # Clean divider and headers
    ax.axhline(2.8, color="#B0BEC5", linestyle="--", linewidth=0.8, alpha=0.7)
    ax.text(12, 6.55, "Retrieval-Only Stages (CPU, 95% Bootstrap CIs)",
            fontsize=7.8, fontweight="bold", color="#455A64", va="bottom")
    ax.text(12, 2.45, "Full Pipeline End-to-End (GPU+CPU, Medians, LLM Generation Included)",
            fontsize=7.8, fontweight="bold", color="#455A64", va="bottom")

    # Deployment Footprint card in whitespace at top right
    info_text = (
        r"$\mathbf{Deployment\;Footprint}$" + "\n"
        "─────────────────────────\n"
        "Peak Host RSS: 8,950 MB\n"
        "GPU VRAM:      4,710 MB\n"
        "Cold Start:    18.66 s\n"
        "Amortised: 0.037 s/q @ N=500"
    )
    ax.text(80000, 5.2, info_text, va="center", ha="right", fontsize=7.0,
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#F8FAFC", edgecolor="#B0BEC5", linewidth=0.8),
            zorder=5)

    ax.set_yticks(y_positions)
    ax.set_yticklabels([e[0] for e in entries], fontsize=8.0)
    ax.set_xlabel("Execution Latency (ms, Logarithmic Scale)", fontsize=9.0)
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax.set_xlim(10, 100000)
    ax.set_ylim(-0.2, 7.1)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="x", color="#CCCCCC", linestyle=":", linewidth=0.5, alpha=0.6, which="both")

    out = OUT_DIR / "fig_latency.pdf"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"✓  {out.name}")


# ══════════════════════════════════════════════════════════════════════════════
# Main Execution
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("MedGraphRAG IJMI — Figure Generator")
    print(f"Output directory: {OUT_DIR.resolve()}\n")

    try:
        calib, s500, v_abl, r_abl, comp = load_data()
        make_arch_figure()
        make_pareto_figure(calib, s500)
        make_ablation_figure(v_abl, r_abl, s500)
        make_latency_figure(comp)
    except FileNotFoundError as e:
        print(f"\n[ERROR] Missing evaluation artifact: {e}", file=sys.stderr)
        sys.exit(1)

    print("\nAll figures generated successfully.")
