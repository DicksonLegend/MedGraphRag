#!/usr/bin/env python3
"""
make_coverage_heatmap.py
-------------------------
Reads evaluations/step13_features_report.json and plots a compact landscape
HEATMAP of sub-question coverage metrics designed for 1:1 IEEE text width (7.16 in).

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
    # Truncate to ~60 chars and wrap into at most 2 lines
    if len(raw_text) > 60:
        truncated_text = raw_text[:57] + "..."
    else:
        truncated_text = raw_text
    wrapped = textwrap.fill(truncated_text, width=48)
    row_labels.append(f"SQ{idx}: {wrapped}")
    
    score = float(sq["top_fused_score"])
    docs = int(sq["distinct_doc_count"])
    c_class = sq["coverage_class"]
    c_code = class_map.get(c_class.lower(), 1.0)
    
    matrix_data.append([score, docs, c_code])
    annotations.append([f"{score:.4f}", f"{docs}", c_class.capitalize()])

matrix_np = np.array(matrix_data)

# Normalize each column to [0, 1] for balanced heatmap rendering across different metric scales
norm_matrix = np.zeros_like(matrix_np)
for j in range(matrix_np.shape[1]):
    col_min = matrix_np[:, j].min()
    col_max = matrix_np[:, j].max()
    if col_max > col_min:
        norm_matrix[:, j] = (matrix_np[:, j] - col_min) / (col_max - col_min)
    else:
        norm_matrix[:, j] = 1.0  # Constant high intensity if all identical (e.g. all 10 docs, all strong)

col_labels = ["Top Fused Score", "Distinct Docs", "Coverage Class"]

# Compact landscape figure geometry: 7.16 in width x 2.4 in height (fits full text width)
fig, ax = plt.subplots(figsize=(7.16, 2.4))
ax.set_aspect("auto")

cax = ax.imshow(norm_matrix, cmap="viridis", aspect="auto", vmin=0, vmax=1.1)

# Set ticks and labels with precise font sizes
ax.set_xticks(np.arange(len(col_labels)))
ax.set_yticks(np.arange(len(row_labels)))
ax.set_xticklabels(col_labels, fontsize=8, fontweight="bold")
ax.set_yticklabels(row_labels, fontsize=7)

# Add cell annotations
for i in range(len(row_labels)):
    for j in range(len(col_labels)):
        text_val = annotations[i][j]
        # Choose text color based on cell intensity for optimal contrast
        text_color = "white" if norm_matrix[i, j] < 0.60 else "black"
        ax.text(
            j, i, text_val,
            ha="center", va="center",
            fontsize=8,
            fontweight="bold",
            color=text_color
        )

ax.set_title(
    "Evidence Coverage per Sub-Question (Feature Layer)\nsource: evaluations/step13_features_report.json",
    fontsize=9,
    fontweight="bold",
    pad=8
)

# Thin vertical colorbar on the right
cbar = fig.colorbar(cax, ax=ax, orientation="vertical", pad=0.02, shrink=0.92, aspect=18)
cbar.set_label("Relative Strength", fontsize=7)
cbar.set_ticks([0.0, 0.5, 1.0])
cbar.set_ticklabels(["Low", "Mid", "Strong"], fontsize=7)

plt.tight_layout()
plt.savefig(OUT_PATH, format="pdf", bbox_inches="tight")
print(f"Saved: {OUT_PATH}")
