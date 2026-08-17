#!/usr/bin/env python3
"""
make_tradeoff_chart.py
----------------------
Reads evaluations/step12_part3_paper_tables.json (relative to the
MedGraphRAG project root) and plots a grouped bar chart of
Wrong Assertion Rate vs Refusal Rate per ablation configuration.

Output: figures/tradeoff_chart.pdf  (vector, IEEE-ready)

Usage (from project root):
    python conference_paper/figures/make_tradeoff_chart.py

Requirements: matplotlib, numpy (both in standard scientific Python envs)
"""

import json
import pathlib
import sys

import matplotlib
matplotlib.use("Agg")          # non-interactive backend, safe for headless runs
import matplotlib.pyplot as plt
import numpy as np

# ── Locate data file ──────────────────────────────────────────────────────────
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent          # conference_paper/figures/
PROJECT_ROOT = SCRIPT_DIR.parent.parent                       # MedGraphRag/
DATA_PATH = PROJECT_ROOT / "evaluations" / "step12_part3_paper_tables.json"
OUT_PATH = SCRIPT_DIR / "tradeoff_chart.pdf"

if not DATA_PATH.exists():
    sys.exit(f"ERROR: data file not found at {DATA_PATH}")

# ── Load data ─────────────────────────────────────────────────────────────────
with open(DATA_PATH, "r") as f:
    data = json.load(f)

rows = data["table_1_ablation_matrix"]

# Extract values in config order C1, C2, C3, C4
configs    = [r["config_id"]           for r in rows]  # ["C1","C2","C3","C4"]
wrong_rate = [r["wrong_assertion_rate"] for r in rows]  # [12.0, 6.0, 48.0, 44.0]
refusal    = [r["refusal_rate"]         for r in rows]  # [82.0, 88.0, 2.0, 2.0]
latency    = [r["median_latency_ms"]    for r in rows]  # for annotation

# Labels shown on x-axis
labels = [
    f"{r['config_id']}\n({r['config_name'].replace('_', ' ')})"
    for r in rows
]

# ── Plot ──────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(7, 4))

x = np.arange(len(configs))
width = 0.35

bars_wrong   = ax.bar(x - width/2, wrong_rate, width,
                      label="Wrong Assertion Rate (%)",
                      color="#D62728", edgecolor="black", linewidth=0.6)
bars_refusal = ax.bar(x + width/2, refusal, width,
                      label="Refusal Rate (%)",
                      color="#1F77B4", edgecolor="black", linewidth=0.6)

# Value labels on bars
for bar in bars_wrong:
    h = bar.get_height()
    ax.text(bar.get_x() + bar.get_width() / 2, h + 0.8,
            f"{h:.0f}%", ha="center", va="bottom", fontsize=8)

for bar in bars_refusal:
    h = bar.get_height()
    ax.text(bar.get_x() + bar.get_width() / 2, h + 0.8,
            f"{h:.0f}%", ha="center", va="bottom", fontsize=8)

ax.set_xlabel("Ablation Configuration", fontsize=10)
ax.set_ylabel("Rate (%)", fontsize=10)
ax.set_title(
    "MedGraphRAG Ablation: Wrong Assertion Rate vs. Refusal Rate\n"
    r"MedQA-US $N=50$, seed 42 — "
    "source: evaluations/step12_part3_paper_tables.json",
    fontsize=9
)
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=8)
ax.set_ylim(0, 105)
ax.legend(fontsize=9)
ax.yaxis.grid(True, linestyle="--", alpha=0.5)
ax.set_axisbelow(True)

# Annotate median latency below each group
for i, (cfg, lat) in enumerate(zip(configs, latency)):
    ax.annotate(
        f"Lat: {lat/1000:.1f}s",
        xy=(x[i], -9), xycoords=("data", "axes fraction"),
        ha="center", va="top", fontsize=7, color="#555555",
        annotation_clip=False
    )

plt.subplots_adjust(left=0.10, right=0.97, top=0.88, bottom=0.18)
plt.savefig(str(OUT_PATH), format="pdf", dpi=300, bbox_inches="tight")
print(f"Saved: {OUT_PATH}")
