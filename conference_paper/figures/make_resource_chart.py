#!/usr/bin/env python3
"""
make_resource_chart.py
-----------------------
Reads hardware resource measurements from evaluations/step12_part3_paper_tables.json
and plots a RADAR / SPIDER chart of Measured vs. Budget across 5 axes.

Output: figures/resource_chart.pdf  (vector, IEEE-ready)

Usage (from project root):
    python conference_paper/figures/make_resource_chart.py
"""

import json
import pathlib
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DATA_PATH = PROJECT_ROOT / "evaluations" / "step12_part3_paper_tables.json"
OUT_PATH = SCRIPT_DIR / "resource_chart.pdf"

if not DATA_PATH.exists():
    sys.exit(f"ERROR: data file not found at {DATA_PATH}")

with open(DATA_PATH, "r") as f:
    data = json.load(f)

res = data["table_4_resource_profile"]

# Dynamically extract measured values and limits from JSON
ram_meas = float(res["system_ram_peak_gb"])
ram_budg = float(res["system_ram_limit_gb"])

vram_meas = float(res["gpu_vram_peak_mb"]) / 1024.0
vram_budg = float(res["gpu_vram_limit_mb"]) / 1024.0

faiss_meas = float(res["faiss_index_memory_mb"]) / 1024.0
faiss_budg = 1.0  # Normalized reference ceiling (1.0 GB CPU budget)

kuzu_meas = float(res["kuzu_graph_memory_mb"]) / 1024.0
kuzu_budg = 1.0   # Normalized reference ceiling (1.0 GB CPU mmap budget)

llm_meas = float(res["llm_concurrent_calls"])
llm_budg = float(res["llm_concurrent_calls"])

# Axis definitions
categories = [
    "Peak RAM\n(GB)",
    "Peak VRAM\n(GB)",
    "FAISS Index\n(GB)",
    "Kùzu Graph\n(GB)",
    "LLM Instances\n(Count)"
]
N = len(categories)

measured_raw = [ram_meas, vram_meas, faiss_meas, kuzu_meas, llm_meas]
budget_raw = [ram_budg, vram_budg, faiss_budg, kuzu_budg, llm_budg]

# Normalized values relative to budget [0.0, 1.0]
measured_norm = [min(m / b, 1.0) for m, b in zip(measured_raw, budget_raw)]
budget_norm = [1.0] * N

# Radar angles
angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
# Close polygon loop
measured_norm += measured_norm[:1]
budget_norm += budget_norm[:1]
angles += angles[:1]

fig, ax = plt.subplots(figsize=(6.5, 5.5), subplot_kw=dict(polar=True))

# Draw budget outline
ax.plot(angles, budget_norm, color="#7F7F7F", linewidth=1.5, linestyle="--", label="Budget Ceiling (1.0x)")
ax.fill(angles, budget_norm, color="#E0E0E0", alpha=0.15)

# Draw measured polygon
ax.plot(angles, measured_norm, color="#008080", linewidth=2.0, label="Measured Utilization")
ax.fill(angles, measured_norm, color="#008080", alpha=0.40)

# Set category labels
ax.set_xticks(angles[:-1])
ax.set_xticklabels(categories, fontsize=8.5, fontweight="medium")

# Customize radial grid
ax.set_rlabel_position(30)
ax.set_yticks([0.25, 0.50, 0.75, 1.00])
ax.set_yticklabels(["25%", "50%", "75%", "100%"], fontsize=7, color="#666666")
ax.set_ylim(0, 1.15)

# Annotate raw values at vertices
for i in range(N):
    ang = angles[i]
    m_val = measured_raw[i]
    b_val = budget_raw[i]
    if i in [0, 1]:
        txt = f"{m_val:.2f} / {b_val:.1f} GB"
    elif i in [2, 3]:
        txt = f"{m_val*1024:.0f} MB / {b_val:.1f} GB"
    else:
        txt = f"{int(m_val)} / {int(b_val)}"
        
    r_pos = measured_norm[i]
    # Place text with slight outward radial offset
    ax.text(
        ang, r_pos + 0.10,
        txt,
        ha="center",
        va="center",
        fontsize=7.5,
        fontweight="bold",
        color="#004D40",
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="#008080", alpha=0.85, lw=0.6)
    )

ax.set_title(
    "Consumer Hardware Resource Footprint (Measured vs Budget)\n"
    "source: step12_part3_paper_tables.json, step11_api_report.json, step13_features_report.md",
    fontsize=9,
    pad=20
)

ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1), fontsize=8)
plt.tight_layout()
plt.savefig(OUT_PATH, format="pdf", bbox_inches="tight")
print(f"Saved: {OUT_PATH}")
