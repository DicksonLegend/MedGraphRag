#!/usr/bin/env python3
"""
make_disposition_chart.py
--------------------------
Reads evaluations/step12_part3_paper_tables.json (relative to the
MedGraphRAG project root) and plots a stacked bar chart showing
correct / wrong-asserted / refused query counts per ablation configuration.

Counts are computed from percentages × N=50; no values are hard-coded.

Output: figures/disposition_chart.pdf  (vector, IEEE-ready)

Usage (from project root):
    python conference_paper/figures/make_disposition_chart.py
"""

import json
import pathlib
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SCRIPT_DIR   = pathlib.Path(__file__).resolve().parent   # conference_paper/figures/
PROJECT_ROOT = SCRIPT_DIR.parent.parent                  # MedGraphRag/
DATA_PATH    = PROJECT_ROOT / "evaluations" / "step12_part3_paper_tables.json"
OUT_PATH     = SCRIPT_DIR / "disposition_chart.pdf"

if not DATA_PATH.exists():
    sys.exit(f"ERROR: data file not found at {DATA_PATH}")

with open(DATA_PATH, "r") as f:
    data = json.load(f)

rows = data["table_1_ablation_matrix"]

configs = [r["config_id"] for r in rows]
N = 50

# Compute integer counts from percentages × N
# accuracy_all = correct / N × 100  →  correct = acc_all_pct / 100 × N
# wrong_assertion_rate = (answered − correct) / N × 100
#   →  wrong_asserted = war_pct / 100 × N
# refused = N − answered  →  refused = refusal_rate / 100 × N
correct     = [round(r["accuracy_all"]        / 100 * N) for r in rows]
wrong       = [round(r["wrong_assertion_rate"] / 100 * N) for r in rows]
refused     = [round(r["refusal_rate"]         / 100 * N) for r in rows]

labels = [
    f"{r['config_id']}\n({r['config_name'].replace('_', ' ')})"
    for r in rows
]

x = np.arange(len(configs))
width = 0.55

fig, ax = plt.subplots(figsize=(6.5, 4))

bar_ref  = ax.bar(x, refused,  width, label="Refused",       color="#AEC6E8", edgecolor="black", linewidth=0.6)
bar_wrg  = ax.bar(x, wrong,    width, label="Wrong asserted", color="#D62728", edgecolor="black", linewidth=0.6, bottom=refused)
bar_cor  = ax.bar(x, correct,  width, label="Correct",        color="#2CA02C", edgecolor="black", linewidth=0.6,
                  bottom=[r + w for r, w in zip(refused, wrong)])

# Add value labels inside bars
for i, (r, w, c) in enumerate(zip(refused, wrong, correct)):
    if r > 0:
        ax.text(x[i], r / 2,              str(r), ha="center", va="center", fontsize=9, color="black")
    if w > 0:
        ax.text(x[i], r + w / 2,          str(w), ha="center", va="center", fontsize=9, color="white")
    if c > 0:
        ax.text(x[i], r + w + c / 2,      str(c), ha="center", va="center", fontsize=9, color="white")

ax.set_xlabel("Ablation Configuration", fontsize=10)
ax.set_ylabel("Query Count (N=50)", fontsize=10)
ax.set_title(
    "Per-Configuration Disposition: Correct / Wrong / Refused\n"
    r"MedQA-US $N=50$, seed 42 — "
    "source: evaluations/step12_part3_paper_tables.json",
    fontsize=9
)
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=8)
ax.set_ylim(0, 58)
ax.legend(fontsize=9, loc="upper right")
ax.yaxis.grid(True, linestyle="--", alpha=0.4)
ax.set_axisbelow(True)

plt.tight_layout()
plt.savefig(OUT_PATH, format="pdf", bbox_inches="tight")
print(f"Saved: {OUT_PATH}")
