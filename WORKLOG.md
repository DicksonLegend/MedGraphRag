# MedGraphRAG Journal Extension — Worklog
| Phase | Item | Owner | Status | Artifact (sha) | Updated |
|---|---|---|---|---|---|
| A | Onboarding audit | OpenCode | done | — | |
| A | J1 preview | Antigravity | done | read-only preview | 2026-08-22 |
| A | J1 execute + step14 | Antigravity | done | step14_negation_temporal_build.json (f99934e1) | 2026-08-22 |
| A | Downloads + manifest | OpenCode | partial | data/multimodal/MANIFEST.md (OpenI reports+VQA-RAD+MedMCQA+CLIP+Qwen2-VL done; SLAKE retry pending) | 2026-08-23 |
| B | J9 OpenI normalize (reports→chunks) | OpenCode | done | data/multimodal/chunks/openi_chunks.jsonl (f59560a3) | 2026-08-23 |
| B | J2/J3 execute | Antigravity | | step15 blocks | |
| B | VLM + image eval | OpenCode | | step16_image_report | |
| C | N=500 + stats | Antigravity | | step15_scaled_eval | |
| B | J2 graph-consistency verification pass + 3-way ablation | Antigravity | done | step15_verification_ablation.json (e01fe516) | 2026-08-22 |
| B | J3 relation-aware reranker vs RRF ablation | Antigravity | done | step15_rerank_ablation.json (eda10b8e) | 2026-08-23 |
| B | J9 OpenI/VQA-RAD/SLAKE normalize + CheXzero encode | OpenCode | partial | openi_chunks.jsonl (f59560a3) + visual_findings.json (17a3ee96); SLAKE deferred (GDrive quota) | 2026-08-23 |
| B | J9 separate report graph build (Image/VisualFinding nodes) | OpenCode | done* | data/multimodal/report_graph/kuzu.db (315 img/4410 find/11211 rpt; cross-links pending NLMCXR sample100) | 2026-08-23 |
| B | J9/J10 Qwen2-VL-2B endpoints + image-aware /query + refusal | OpenCode | blocked | step16_image_report.json — llama_cpp MISSING in Data_Normalization venv; needs approval to install | 2026-08-23 |
| C | J4 MedQA-US N=500 scaled eval (overnight batch) | Antigravity | pending | step15_scaled_eval.json | |
| C | J5 MedMCQA (+BioASQ optional) external validation | Antigravity | pending | step15_external_eval.json | |
| C | J6 IR metrics (P@5/R@5/MRR/nDCG@10) + hallucination rates | OpenCode | done* | evaluations/multimodal/step17_ir_metrics.json (bac17814; proxy lexical qrels — NOT publication-grade) | 2026-08-23 |
| C | J7 task-slice eval (negation/temporal/severity/finding–anatomy) | Antigravity | pending | step15_task_slices.json | |
| C | J8 baselines suite (BM25/Dense/Hybrid/GraphRAG/MedRAG/Self-RAG) | OpenCode | done | evaluations/baselines/baseline_retrieval_results.json (sha c500e55a) | 2026-08-23 |
| C | J4-stats bootstrap CIs (1000 resamples, seed 42) | Antigravity | pending | step15_bootstrap_ci.json | |
| D | J11 multi-turn clinician workflows | OpenCode | pending | step18_multiturn.json | |
| D | J12 batched verification (latency fix) | Antigravity | pending | step15_batched_verify.json | |
| D | J13 compute comparison table vs baselines | Antigravity | pending | step15_compute_table.json | |
| D | Regression sweep (step12/13 values unchanged post-J1–J3) | Antigravity | pending | regression_final.json | |
| E | J14 ethics/data-availability/AI-disclosure sections | Antigravity | pending | journal_paper/main.tex §updates | |
| E | J14 UI screenshot (`fig:ui`) for journal | Antigravity | pending | figures/fig_ui.png | |
| E | J16 citations (AMG-RAG, Rethinking-RAG, MediGRAF-Frontiers) | Antigravity | pending | references.bib updates | |
| E | J17 journal title/abstract rework | Antigravity | pending | journal_paper/main.tex §title+abstract | |
| E | Journal draft (12 pages) writing | Antigravity + you | pending | journal_paper/main.tex | |
| E | Journal figures (5 conference + multimodal arch + 3 result figs) | you | pending | figures/ | |
| F | Guide review + revisions | you | pending | — | |
| F | AI + similarity checks (Turnitin/iThenticate) | you | pending | — | |
| F | Repo public flip (at acceptance) | you | pending | github.com/... | |
| F | Submit | you | pending | — | |