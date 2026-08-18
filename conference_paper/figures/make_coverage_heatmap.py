#!/usr/bin/env python3
"""
make_coverage_heatmap.py
-------------------------
Reads evaluations/step13_features_report.json and plots a HEATMAP of
sub-question coverage metrics across all query probes in the feature evaluation.

Output: figures/coverage_heatmap.pdf  (vector, IEEE-ready)

Usage (from project root):
    python conference_paper/figures/make_coverage_heatmap.py
"""

import json
import pathlib
import sys
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DATA_PATH = PROJECT_ROOT / "evaluations" / "step13_features_report.json"
OUT_PATH = SCRIPT_DIR / "coverage_heatmap.pdf"

if not DATA_PATH.exists():
    sys.exit(f"ERROR: data file not found at {DATA_PATH}")

with open(DATA_PATH, "r") as f:
    data = json.load(f)

cov = data["feature_3_coverage_map"]

# Collect all sub-questions from both c1_subquestions and c2_subquestions
subquestions = []
for item in cov.get("c1_subquestions", []):
    subquestions.append(item)
for item in cov.get("c2_subquestions", []):
    subquestions.append(item)

# Class mapping to numeric scale
class_map = {"none": 0.0, "partial": 1.0, "strong": 2.0}

row_labels = []
matrix_data = []
annotations = []

for idx, sq in enumerate(subquestions, 1):
    raw_text = sq["sub_question"]
    # Wrap and truncate text
    wrapped = textwrap.fill(raw_text, width=42)
    row_labels.append(f"SQ{idx}: {wrapped}")
    
    score = float(sq["top_fused_score"])
    docs = int(sq["distinct_doc_count"])
    c_class = sq["coverage_class"]
    c_code = class_map.get(c_class.lower(), 1.0)
    
    matrix_data.append([score, docs, c_code])
    annotations.append([f"{score:.4f}", f"{docs}", c_class.capitalize()])

matrix_np = np.array(matrix_data)

# Normalize each column to [0, 1] for balanced heatmap rendering
norm_matrix = np.zeros_like(matrix_np)
for j in range(matrix_np.shape[1]):
    col_min = matrix_np[:, j].min()
    col_max = matrix_np[:, j].max()
    if col_max > col_min:
        norm_matrix[:, j] = (matrix_np[:, j] - col_min) / (col_max - col_min)
    else:
        norm_matrix[:, j] = 1.0  # Constant high value if all identical (e.g. all 10 docs, all strong)

col_labels = ["Top Fused Score", "Distinct Docs", "Coverage Class"]

fig, ax = plt.subplots(figsize=(7.5, 4.8))

cax = ax.imshow(norm_matrix, cmap="YlGnBu", aspect="auto", vmin=0, vmax=1.2)

# Set ticks and labels
ax.set_xticks(np.arange(len(col_labels)))
ax.set_yticks(np.arange(len(row_labels)))
ax.set_xticklabels(col_labels, fontsize=9.5, fontweight="semibold")
ax.set_yticklabels(row_labels, fontsize=8)

# Add cell annotations
for i in range(len(row_labels)):
    for j in range(len(col_labels)):
        text_val = annotations[i][j]
        # Choose text color based on cell intensity
        text_color = "white" if norm_matrix[i, j] > 0.65 else "#111111"
        ax.text(
            j, i, text_val,
            ha="center", va="center",
            fontsize=8.5,
            fontweight="bold",
            color=text_color
        )

ax.set_title(
    "Evidence Coverage per Sub-Question (Feature Layer)\n"
    "source: evaluations/step13_features_report.json",
    fontsize=9.5,
    pad=12
)

# Add a colorbar
cbar = fig.colorbar(cax, ax=ax, orientation="vertical", pad=0.03, shrink=0.85)
cbar.set_label("Relative Evidence Strength", fontsize=8)
cbar.set_ticks([0.0, 0.5, 1.0])
cbar.set_ticklabels(["Baseline", "Moderate", "Max/Strong"], fontsize=7.5)

plt.tight_layout()
plt.savefig(OUT_PATH, format="pdf", bbox_inches="tight")
print(f"Saved: {OUT_PATH}")
