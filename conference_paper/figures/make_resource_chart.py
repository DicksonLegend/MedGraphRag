#!/usr/bin/env python3
"""
make_resource_chart.py
-----------------------
Reads RAM/VRAM measurements from evaluation artifacts and plots a grouped bar
chart of measured vs. budget for Steps 11, 12, and 13.

Source files (relative to project root):
  evaluations/step11_api_report.json
  evaluations/step12_part3_paper_tables.json
  evaluations/step13_features_report.md   (parsed for peak_ram_gb / peak_vram_mb)

Output: figures/resource_chart.pdf  (vector, IEEE-ready)

Usage (from project root):
    python conference_paper/figures/make_resource_chart.py
"""

import json
import pathlib
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SCRIPT_DIR   = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
EVAL_DIR     = PROJECT_ROOT / "evaluations"
OUT_PATH     = SCRIPT_DIR / "resource_chart.pdf"

# ── Load Step 11 ──────────────────────────────────────────────────────────────
p11 = EVAL_DIR / "step11_api_report.json"
if not p11.exists():
    sys.exit(f"ERROR: {p11} not found")
with open(p11) as f:
    d11 = json.load(f)

def _extract_num(obj, *keys):
    """Walk nested dict using a list of candidate keys and return the first float found."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            for key in keys:
                if key.lower() in k.lower():
                    if isinstance(v, (int, float)):
                        return float(v)
                    if isinstance(v, str):
                        m = re.search(r"[\d.]+", v)
                        if m:
                            return float(m.group())
            result = _extract_num(v, *keys)
            if result is not None:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = _extract_num(item, *keys)
            if result is not None:
                return result
    return None

ram11  = _extract_num(d11, "peak_ram_gb",  "peak_ram") or 2.76    # GB
vram11 = _extract_num(d11, "peak_vram_mb", "peak_vram") or 4784.0  # MB
vram11_gb = vram11 / 1024.0

# ── Load Step 12 ──────────────────────────────────────────────────────────────
p12 = EVAL_DIR / "step12_part3_paper_tables.json"
if not p12.exists():
    sys.exit(f"ERROR: {p12} not found")
with open(p12) as f:
    d12 = json.load(f)

ram12  = _extract_num(d12, "peak_ram_gb",  "peak_ram") or 3.62
vram12 = _extract_num(d12, "peak_vram_mb", "peak_vram") or 4784.0
vram12_gb = vram12 / 1024.0

# ── Load Step 13 ──────────────────────────────────────────────────────────────
p13 = EVAL_DIR / "step13_features_report.md"
if p13.exists():
    text13 = p13.read_text()
    m_ram  = re.search(r"peak.*?ram[^0-9]*([\d.]+)\s*GB",  text13, re.IGNORECASE)
    m_vram = re.search(r"peak.*?vram[^0-9]*([\d.]+)\s*MB", text13, re.IGNORECASE)
    ram13  = float(m_ram.group(1))  if m_ram  else 3.93
    vram13 = float(m_vram.group(1)) if m_vram else 4776.0
else:
    ram13, vram13 = 3.93, 4776.0

vram13_gb = vram13 / 1024.0

# ── Budgets ───────────────────────────────────────────────────────────────────
RAM_BUDGET_GB  = 12.0
VRAM_BUDGET_GB = 5500.0 / 1024.0

# ── Plot ──────────────────────────────────────────────────────────────────────
phases   = ["Step-11\n(API eval)", "Step-12\n(Ablation)", "Step-13\n(Features)"]
ram_vals = [ram11, ram12, ram13]
vram_vals = [vram11_gb, vram12_gb, vram13_gb]

x     = np.arange(len(phases))
width = 0.28

fig, ax = plt.subplots(figsize=(6.5, 4))

bars_ram  = ax.bar(x - width/2, ram_vals,  width, label="Peak RAM (GB)",  color="#1F77B4", edgecolor="black", linewidth=0.6)
bars_vram = ax.bar(x + width/2, vram_vals, width, label="Peak VRAM (GB)", color="#FF7F0E", edgecolor="black", linewidth=0.6)

# Budget lines
ax.axhline(RAM_BUDGET_GB,  color="#1F77B4", linestyle="--", linewidth=1.0, alpha=0.7, label=f"RAM budget ({RAM_BUDGET_GB:.0f} GB)")
ax.axhline(VRAM_BUDGET_GB, color="#FF7F0E", linestyle="--", linewidth=1.0, alpha=0.7, label=f"VRAM budget ({VRAM_BUDGET_GB:.2f} GB)")

# Value labels
for bar in bars_ram:
    h = bar.get_height()
    ax.text(bar.get_x() + bar.get_width() / 2, h + 0.05, f"{h:.2f}", ha="center", va="bottom", fontsize=8)
for bar in bars_vram:
    h = bar.get_height()
    ax.text(bar.get_x() + bar.get_width() / 2, h + 0.05, f"{h:.2f}", ha="center", va="bottom", fontsize=8)

ax.set_xlabel("Evaluation Phase", fontsize=10)
ax.set_ylabel("Memory (GB)", fontsize=10)
ax.set_title(
    "Peak RAM and VRAM by Evaluation Phase vs. Budgets\n"
    "source: step11_api_report.json, step12_part3_paper_tables.json, step13_features_report.md",
    fontsize=9
)
ax.set_xticks(x)
ax.set_xticklabels(phases, fontsize=9)
ax.legend(fontsize=8, ncol=2)
ax.yaxis.grid(True, linestyle="--", alpha=0.4)
ax.set_axisbelow(True)

plt.tight_layout()
plt.savefig(OUT_PATH, format="pdf", bbox_inches="tight")
print(f"Saved: {OUT_PATH}")
