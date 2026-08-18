#!/usr/bin/env python3
"""
make_tradeoff_chart.py
----------------------
Reads evaluations/step12_part3_paper_tables.json (relative to the
MedGraphRAG project root) and plots a SCATTER plot of
Wrong Assertion Rate vs Refusal Rate across ablation configurations.

Output: figures/tradeoff_chart.pdf  (vector, IEEE-ready)

Usage (from project root):
    python conference_paper/figures/make_tradeoff_chart.py
"""

import json
import pathlib
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DATA_PATH = PROJECT_ROOT / "evaluations" / "step12_part3_paper_tables.json"
OUT_PATH = SCRIPT_DIR / "tradeoff_chart.pdf"

if not DATA_PATH.exists():
    sys.exit(f"ERROR: data file not found at {DATA_PATH}")

with open(DATA_PATH, "r") as f:
    data = json.load(f)

rows = data["table_1_ablation_matrix"]

# Extract values dynamically
configs = [r["config_id"] for r in rows]
names = [r["config_name"] for r in rows]
wrong_rate = [r["wrong_assertion_rate"] for r in rows]
refusal_rate = [r["refusal_rate"] for r in rows]
latencies = [r["median_latency_ms"] for r in rows]

fig, ax = plt.subplots(figsize=(7, 4.5))

# Shade the "ideal safety zone" (refusal >= 70%, wrong_assertion <= 15%)
safe_zone = patches.Rectangle(
    (70, 0), 32, 15,
    linewidth=1.2,
    edgecolor="#2CA02C",
    facecolor="#D5F5E3",
    alpha=0.45,
    linestyle="--",
    label="Safe operating region"
)
ax.add_patch(safe_zone)
ax.text(86, 7.5, "Safe operating\nregion", ha="center", va="center",
        fontsize=8.5, color="#196F3D", fontweight="bold", style="italic")

# Distinct markers and colors for each configuration (grayscale & color safe)
markers = {"C1": "o", "C2": "s", "C3": "^", "C4": "D"}
colors = {"C1": "#1F77B4", "C2": "#2CA02C", "C3": "#FF7F0E", "C4": "#D62728"}

c_coords = {}
for r in rows:
    cid = r["config_id"]
    x = r["refusal_rate"]
    y = r["wrong_assertion_rate"]
    lat_s = r["median_latency_ms"] / 1000.0
    c_coords[cid] = (x, y)
    
    ax.scatter(
        x, y,
        s=140,
        marker=markers[cid],
        color=colors[cid],
        edgecolor="black",
        linewidth=1.0,
        zorder=5,
        label=f"{cid} ({r['config_name'].replace('_', ' ')})"
    )
    
    # Label placement offset
    x_offset = 2.5 if x < 50 else -2.5
    ha = "left" if x < 50 else "right"
    if cid == "C3":
        y_offset = 2.0
    elif cid == "C4":
        y_offset = -3.0
    elif cid == "C1":
        y_offset = 2.5
    else:
        y_offset = -3.0
        
    ax.annotate(
        f"{cid} ({lat_s:.1f}s)",
        xy=(x, y),
        xytext=(x + x_offset, y + y_offset),
        ha=ha,
        va="center",
        fontsize=8.5,
        fontweight="semibold",
        color="#222222"
    )

# Draw arrow from C4 (baseline) to C1 (full verified)
if "C4" in c_coords and "C1" in c_coords:
    ax.annotate(
        "Verification enabled",
        xy=c_coords["C1"],
        xytext=(c_coords["C4"][0] + 15, c_coords["C4"][1] - 12),
        arrowprops=dict(
            arrowstyle="->",
            color="#1F77B4",
            lw=1.6,
            linestyle="--",
            connectionstyle="arc3,rad=-0.22"
        ),
        fontsize=8.5,
        color="#1F77B4",
        fontweight="bold",
        ha="left",
        va="center"
    )

ax.set_xlabel("Refusal Rate (%)", fontsize=10)
ax.set_ylabel("Wrong Assertion Rate (%)", fontsize=10)
ax.set_xlim(-5, 105)
ax.set_ylim(-3, 58)

ax.set_title(
    "MedGraphRAG Safety Frontier: Refusal vs Wrong-Assertion Rate\n"
    r"MedQA-US $N=50$, seed 42 — "
    "source: evaluations/step12_part3_paper_tables.json",
    fontsize=9
)

ax.grid(True, linestyle=":", alpha=0.6)
ax.set_axisbelow(True)
ax.legend(loc="upper right", fontsize=8, framealpha=0.9)

plt.tight_layout()
plt.savefig(OUT_PATH, format="pdf", bbox_inches="tight")
print(f"Saved: {OUT_PATH}")
