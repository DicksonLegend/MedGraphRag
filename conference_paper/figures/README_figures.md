# MedGraphRAG Conference Paper — Figures

This document lists every figure referenced in `main.tex`, the exact data
source for each, and instructions for producing the final PDF/PNG.

> **Rule**: Every figure must be generated from evaluation JSON/Markdown files.
> Never hard-code a number that is not directly read from a source file.

---

## Figure 1 — System Architecture Diagram

**Caption (as used in paper):**  
*MedGraphRAG end-to-end pipeline: query enters the FastAPI service layer,
passes through (A) Hybrid Retrieval, (B) Context Assembly, (C) LLM Generation,
and (D) Verification Agent, with results stored in the AES-256-GCM encrypted
private store.*

**Data sources:** None (architecture diagram, drawn manually or with a tool).

**How to make:**
- Use draw.io, Inkscape, or PowerPoint.
- Export as `figures/arch_diagram.pdf` (vector) or `figures/arch_diagram.png`
  (300 dpi minimum).
- Include the following boxes with arrows left-to-right:
  1. **FastAPI (v1.0.0)** — JWT Auth, Serialisation Lock
  2. **(A) Hybrid Retrieval** — FAISS IVFpq (2.29M vectors, 240 MB) +
     Kùzu Graph (2.50M nodes, 180 MB) + RRF Fusion + Contamination Guard
  3. **(B) Context Assembly** — Top-10 chunks, evidence labels [E1]–[E10]
  4. **(C) LLM Generation** — Qwen2.5-7B Q4_K_M GGUF, T=0.0
  5. **(D) Verification Agent** — LangGraph, confidence tier, refusal logic
  6. **Private Store** — AES-256-GCM, per-user isolation
- Add resource callout box: RAM 3.62 GB peak | VRAM 4,784 MB peak

**LaTeX inclusion:**
```latex
\begin{figure}[t]
  \centering
  \includegraphics[width=\columnwidth]{figures/arch_diagram.pdf}
  \caption{MedGraphRAG end-to-end pipeline \ldots}
  \label{fig:arch}
\end{figure}
```

---

## Figure 2 — Ablation Trade-off Chart (grouped bar chart)

**Caption (as used in paper):**  
*Ablation results on MedQA-US (N=50). Grouped bars show Wrong Assertion Rate
and Refusal Rate per configuration. Source:
\texttt{evaluations/step12\_part3\_paper\_tables.json}.*

**Data source:** `evaluations/step12_part3_paper_tables.json`  
- `table_1_ablation_matrix[*].wrong_assertion_rate`  
- `table_1_ablation_matrix[*].refusal_rate`
- `table_1_ablation_matrix[*].config_id`

**How to make:** Run `figures/make_tradeoff_chart.py` (see that file).

**Output:** `figures/tradeoff_chart.pdf`

**LaTeX inclusion:**
```latex
\begin{figure}[t]
  \centering
  \includegraphics[width=\columnwidth]{figures/tradeoff_chart.pdf}
  \caption{Ablation trade-off: Wrong Assertion Rate vs.\ Refusal Rate
           per configuration (MedQA-US $N=50$). \ldots}
  \label{fig:tradeoff}
\end{figure}
```

---

## Figure 3 — Resource Footprint Bar Chart (optional)

**Caption:**  
*System resource usage across evaluation steps. Peak RAM and VRAM remain
within budget. Source: \texttt{evaluations/step12\_part3\_paper\_tables.json}
and \texttt{evaluations/step11\_api\_report.json}.*

**Data source:**
- Step 12: RAM 3.62 GB, VRAM 4,784 MB (from `table_4_resource_profile`)
- Step 11: RAM 2.76 GB, VRAM 4,784 MB (from `summary.ram_gb`, `summary.vram_mb`)
- Step 13: RAM 3.93 GB, VRAM 4,776 MB (from `step13_features_report.md` header)

**How to make:** Use matplotlib horizontal bar chart. No script provided;
use the data above directly.

**Output:** `figures/resource_chart.pdf`

---

*End of figures README.*
