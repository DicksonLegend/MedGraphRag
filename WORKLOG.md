# MedGraphRAG Journal Extension — Worklog
| Phase | Item | Owner | Status | Artifact (sha) | Updated |
|---|---|---|---|---|---|
| A | Onboarding audit | OpenCode | done | — | |
| A | J1 preview | Antigravity | done | read-only preview | 2026-08-22 |
| A | J1 execute + step14 | Antigravity | done | step14_negation_temporal_build.json (f99934e1) | 2026-08-22 |
| A | Downloads + manifest | OpenCode | done | data/multimodal/MANIFEST.md — all 7 artifacts full (OpenI reports, VQA-RAD, MedMCQA, CLIP, Qwen2-VL+mmproj, SLAKE via BoKelvin mirror, IU-Xray sample100) | 2026-08-23 |
| B | J9 OpenI normalize (reports→chunks) | OpenCode | done | data/multimodal/chunks/openi_chunks.jsonl (b60730ca; supersedes f59560a3 — image_ids extraction fixed) | 2026-08-23 |
| B | J2/J3 execute | Antigravity | | step15 blocks | |
| B | VLM + image eval | OpenCode | done | evaluations/multimodal/step16_image_report.json (3bede101) — merged into J9/J10 row below | 2026-08-23 |
| C | N=500 + stats | Antigravity | | step15_scaled_eval | |
| B | J2 graph-consistency verification pass + 3-way ablation | Antigravity | done | step15_verification_ablation.json (e01fe516) | 2026-08-22 |
| B | Phase 1 verification autopsy (J2 paradox resolution) | Antigravity | done | evaluations/phase1_verification_autopsy.json (9be1bdf6) — Type A=0, Precision=100%, McNemar p=1.00 (non-sig) | 2026-08-25 |
| B | J3 relation-aware reranker vs RRF ablation | Antigravity | done | step15_rerank_ablation.json (eda10b8e) | 2026-08-23 |
| B | J9 OpenI/VQA-RAD/SLAKE normalize + CheXzero encode | OpenCode | done | openi_chunks.jsonl (b60730ca, image_ids fixed) + visual_findings_v2.json (67f169e6, BiomedCLIP, mean AUC 0.680>0.65) | 2026-08-23 |
| B | J9 separate report graph build (Image/VisualFinding nodes) | OpenCode | done | data/multimodal/report_graph/kuzu.db — RD=48 FN=321 IS=5810; sample100 real OpenI ids linked (48/100 studies) | 2026-08-23 |
| B | J9/J10 Qwen2-VL-2B endpoints + image-aware /query + refusal | OpenCode | done | evaluations/multimodal/step16_image_report.json (3bede101) — llama-cpp-python 0.3.35 CPU build installed (pre-approved); qwen2-vl-vision, 20 VQA-RAD imgs, mean EM 0.35, refusal tiers live | 2026-08-23 |
| B | Multimodal Full Stack Integration (B1–B6, F1–F6, V1–V5) | Antigravity | done | DICOM min-max windowing preview, BiomedCLIP triage (<1.5s), Qwen2-VL-2B CPU generative reports, AES-256-GCM private scan store, dual-tab ReportsPage, chat scan attachment; 0.00% drift PASS | 2026-08-26 |
| B | Multimodal UX & Robustness Enhancements (Fixes 1–3) | Antigravity | done | 60s VLM soft-timeout + 15s UI notice, permanent private scan isolation banner, 48/100 match rate doc; tsc/vite clean | 2026-08-26 |
| Sec | F-01 Cypher parameterization + injection tests | Antigravity | done | commit 98c0dd6 (tests/test_private_store_injection.py PASS) | 2026-08-26 |
| Sec | F-02 HKDF key derivation + 0600 file perms + migration tool | Antigravity | done | commit 913c60f (backend/app/core/report/crypto.py, scripts/migrate_private_store.py) | 2026-08-26 |
| Sec | F-03 Salted scrypt hashing + rate limiting + dev credentials hint | Antigravity | done | commit 45e7e42 (backend/app/core/auth/passwords.py) | 2026-08-26 |
| Sec | F-04 Cross-user existence walk removal + uniform 404 | Antigravity | done | commit 876f7e3 (backend/app/multimodal/service.py) | 2026-08-26 |
| Sec | F-05 Path parameter regex validation + exact match file lookup | Antigravity | done | commit 1903a5c (multimodal/routes.py, report.py, query.py) | 2026-08-26 |
| Sec | F-06 Magic-byte sniffing + PDF safety caps + requirements.lock | Antigravity | done | commit f4034e1 (backend/app/core/security/validation.py, requirements.lock) | 2026-08-26 |
| Sec | F-07 Fail-fast JWT non-dev validation + rotation doc | Antigravity | done | commit 888dac9 (README.md, config.py) | 2026-08-26 |
| Sec | F-08 Production docs disablement + security headers middleware | Antigravity | done | commit b39a85f (backend/app/main.py) | 2026-08-26 |
| Sec | F-09 Log sanitization for queries, filenames, and PHI payloads | Antigravity | done | commit a5d8efb (query.py, report.py) | 2026-08-26 |
| Sec | F-10 Frontend token storage review | Antigravity | done (deferred) | sessionStorage accepted; decision recorded in SECURITY_AUDIT.md | 2026-08-26 |
| Sec | F-11 Dependency lockfile generation | Antigravity | done | commit f4034e1 (requirements.lock, backend/requirements.lock) | 2026-08-26 |
| Sec | F-12/F-13 Multimodal status protection + pre-push secret scanner | Antigravity | done | commit fa724a4 (.githooks/pre-push, deps.py, multimodal/routes.py) | 2026-08-26 |
| C | J6 IR metrics v2 (user-adjudicated graded qrels) | OpenCode | done | evaluations/multimodal/step17_ir_metrics_v2.json (8a2b8fec): P@5 .18 R@5 .54 MRR .353 nDCG@10 .377 | 2026-08-23 |
| C | J4 MedQA-US N=500 scaled eval (restored GPU clean run) | Antigravity | done | evaluations/step18_scaled_n500.json (04f1d7a6) — M1-M4 full eval on RTX 3050 GPU, N=500 seed 42, 100% CPU match rate, 0.00% drift | 2026-08-27 |
| C | J5 MedMCQA (+BioASQ optional) external validation | Antigravity | pending | step15_external_eval.json | |
| C | J6 IR metrics (P@5/R@5/MRR/nDCG@10) + hallucination rates | OpenCode | done* | evaluations/multimodal/step17_ir_metrics.json (bac17814; proxy lexical qrels — NOT publication-grade) | 2026-08-23 |
| C | J7 task-slice eval (negation/temporal/severity/finding–anatomy) | Antigravity | pending | step15_task_slices.json | |
| C | J8 baselines suite (BM25/Dense/Hybrid/GraphRAG/MedRAG/Self-RAG) | OpenCode | done | step17_baselines.json N=50 seed-42 (artifact 4a944e70); regression ba1b5121 PASS; pilot baseline_retrieval_results.json retained (file sha cad0cc20…; no embedded artifact field — that field exists only in step17_baselines.json) | 2026-08-23 |
| C | J4-stats bootstrap CIs (1000 resamples, seed 42) | Antigravity | done | evaluations/step15_bootstrap_ci.json (04f1d7a6) — 1000 resamples, seed 42 for M1–M4 Acc(all), Acc(ans), Refusal, WAR | 2026-08-27 |
| D | J11 multi-turn clinician workflows | OpenCode | pending | step18_multiturn.json | |
| D | J12 batched verification (latency fix) | Antigravity | pending | step15_batched_verify.json | |
| D | J13 compute comparison table vs baselines | Antigravity | done | step15_compute_table.json (f6baecda) — Latency CIs + LaTeX + Pareto frontier | 2026-08-25 |
| D | Regression sweep (step12/13 values unchanged post-J1–J3) | OpenCode | done | evaluations/regression_final.json — actual==expected ba1b5121, 5/5 PASS, 0.00% DRIFT (artifact 86e800df) | 2026-08-23 |
| D | Phase-2 IR upgrade prep (rubric + 30 queries + retrieval + blank dual-grader sheet + metrics script) | OpenCode | done awaiting human grades | phase2_relevance_rubric.md · phase2_queries.json · phase2_retrieval.json (regression ba1b5121 PASS, deterministic rerun ✓, sha-body 2e23ef89) · phase2_grading_sheet.tsv 294 rows · compute_phase2_metrics.py (NOT run) | 2026-08-23 |
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

---

## Incidents & Resolutions

### 2026-08-26: CPU-Wheel Incident & GPU CUDA Restoration
- **Incident Description**: During earlier multimodal setup, a CPU-only wheel of `llama-cpp-python` (version 0.3.35) was installed in `.venv`. This caused LLM inference during the J4 N=500 evaluation to execute on host CPU threads (~30–40s per query) rather than offloading to the NVIDIA RTX 3050 GPU.
- **Root Cause & Discovery**: `llama_cpp.llama_supports_gpu_offload()` returned `False` due to pre-built CPU binaries lacking CUDA kernels.
- **Resolution & Fix**:
  1. Rebuilt/installed `llama-cpp-python` with CUDA acceleration (`GGML_CUDA=1`, CUDA Toolkit 12.4).
  2. Verified `llama_cpp.llama_supports_gpu_offload() == True` allocating 4.76 GB VRAM on the NVIDIA GeForce RTX 3050 (inference speed: ~2.1s per query, a 15–20x speedup).
  3. Added strict startup assertion `assert llama_cpp.llama_supports_gpu_offload() == True` in `scripts/j4/run_scaled_n500_eval.py` to abort immediately if GPU offloading is not available.
  4. Moved all previous CPU checkpoints to `evaluations/checkpoints_n500_cpu_backup/` (retained for scoring comparison).
  5. Relaunched the clean, memory-hardened N=500 GPU evaluation suite under watchdog supervision across all 4 modes (M1 Evidence, M2 Graph, M3 Combined $\beta=0.7$, M4 Hybrid $\gamma=0.15$).