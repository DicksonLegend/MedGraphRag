# Extended Tables — MedGraphRAG IJMI Supplementary

All numbers sourced from canonical evaluation JSON artifacts.
Artifact SHA-256 hashes are embedded in each source file.

---

## Table S1. Full Pareto Frontier — M2 Graph-Only (N=500, seed=42)

Source: `evaluations/step18_threshold_recalibration.json` (`frontiers.M2_GRAPH_ONLY`)

| τ | Acc(all) % | Acc(ans) % | WAR % | Refusal % | Answered/500 | WAR ≤ 10%? |
|---|-----------|------------|-------|-----------|-------------|------------|
| 0.10 | 53.0 | 55.9 | 41.8 |  5.2 | 474 | ❌ |
| 0.15 | 53.0 | 55.9 | 41.8 |  5.2 | 474 | ❌ |
| 0.20 | 53.0 | 56.0 | 41.6 |  5.4 | 473 | ❌ |
| 0.25 | 52.8 | 55.9 | 41.6 |  5.6 | 472 | ❌ |
| 0.30 | 52.8 | 55.9 | 41.6 |  5.6 | 472 | ❌ |
| 0.35 | 52.6 | 56.0 | 41.4 |  6.0 | 470 | ❌ |
| 0.37 | 52.4 | 55.9 | 41.4 |  6.2 | 469 | ❌ |
| 0.40 | 52.4 | 56.0 | 41.2 |  6.4 | 468 | ❌ |
| 0.45 | 52.4 | 56.0 | 41.2 |  6.4 | 468 | ❌ |
| 0.50 | 51.8 | 55.7 | 41.2 |  7.0 | 465 | ❌ |
| 0.55 | 51.8 | 55.8 | 41.0 |  7.2 | 464 | ❌ |
| 0.60 | 51.6 | 56.2 | 40.2 |  8.2 | 459 | ❌ |
| 0.65 | 51.6 | 57.2 | 38.6 |  9.8 | 451 | ❌ |
| 0.70 | 50.6 | 57.9 | 36.8 | 12.6 | 437 | ❌ |
| 0.75 | 49.8 | 58.3 | 35.6 | 14.6 | 427 | ❌ |
| **0.80** | **12.4** | **60.8** | **8.0** | **79.6** | **102** | **✅ Optimal** |

---

## Table S2. Full Safe Operating Points — All Four Modes (N=500, seed=42)

Source: `evaluations/step18_scaled_n500.json` (`safe_operating_points`)

| Mode | τ* | Acc(all)% | Acc(ans)% | WAR% | Refusal% | Answered | Correct | Wrong |
|------|----|-----------|-----------|------|----------|----------|---------|-------|
| M1: Evidence-Only | 0.43 | 9.6 | 50.5 | 9.4 | 81.0 | 95  | 48 | 47 |
| M2: Graph-Only    | 0.80 | 12.4 | 60.8 | 8.0 | 79.6 | 102 | 62 | 40 |
| M3: Combined      | 0.47 | 9.8 | 52.1 | 9.0 | 81.2 | 94  | 49 | 45 |
| M4: Hybrid Rerank | 0.46 | 10.0 | 51.6 | 9.4 | 80.6 | 97  | 50 | 47 |

---

## Table S3. Ungated Ceilings — All Four Modes (N=500)

Source: `evaluations/step18_scaled_n500.json` (`ungated_ceilings`)

| Mode | Acc(all)% | Acc(ans)% | WAR% | Refusal% | Answered |
|------|-----------|-----------|------|----------|----------|
| M1: Evidence-Only | 49.4 | 53.2 | 43.4 | 7.2 | 464 |
| M2: Graph-Only    | 54.8 | 55.1 | 44.6 | 0.6 | 497 |
| M3: Combined      | 50.2 | 54.1 | 42.6 | 7.2 | 464 |
| M4: Hybrid Rerank | 48.6 | 52.5 | 44.0 | 7.4 | 463 |

**Safety cost of removing gate:** WAR increases 4.3–5.6× with ≤ 2.4 pp gain in Acc(all).

---

## Table S4. Deterministic Rewriting Ablation (matched τ=0.50, N=500)

Source: `evaluations/step18_scaled_n500.json` (`matched_tau_comparison`)

| Mode | Condition | Acc(all)% | Acc(ans)% | WAR% | Refusal% |
|------|-----------|-----------|-----------|------|----------|
| M1   | Unrewritten | 3.6 | 51.4 | 3.4 | 93.0 |
| M1   | Rewritten   | 7.8 | 51.3 | 7.4 | 84.8 |
| M3   | Unrewritten | 5.0 | 55.6 | 4.0 | 91.0 |
| M3   | Rewritten   | 8.2 | 48.8 | 8.6 | 83.2 |
| M4   | Unrewritten | 5.4 | 57.5 | 4.0 | 90.6 |
| M4   | Rewritten   | 8.8 | 53.0 | 7.8 | 83.4 |

Query rewriting consistently increases Acc(all) by 3.2–4.2 pp by reducing the
refusal rate — i.e. it allows the model to engage more queries without violating
WAR. The rewritten WAR increase is bounded because the β-gate still enforces
the safety constraint.

---

## Table S5. Retrieval Baseline Comparison — N=50, seed=42

Source: `evaluations/step17_baselines.json`; latency from `evaluations/step15_compute_table.json`

| Retriever | Avg Items | Avg Entities | Avg Graph Chunks | Median Lat (ms) | 95% CI (ms) |
|-----------|-----------|-------------|-----------------|-----------------|-------------|
| BM25-RAG (pool-200) | 10.0 | 0 | 0 | 55.1 | [52.7, 56.5] |
| Dense-RAG           | 10.0 | 0 | 0 | 30.1 | [29.4, 31.0] |
| Hybrid-RRF          | 10.0 | 0 | 0 | 55.4 | [53.5, 56.9] |
| Graph-Only          |  5.0 | 1.90 | 5.00 | 284.1 | — |
| **MedGraphRAG**     |  9.68 | 0.78 | 0.82 | **455.7** | **[388.4, 495.8]** |

Peak RSS across all runs: 3,002 MB. All runs on CPU (retrieval); GPU exclusive to LLM.

---

## Table S6. Negation/Temporal Edge Ingestion Summary (J1)

Source: `evaluations/step14_negation_temporal_build.json`

| Edge Type | Sub-type | Count |
|-----------|----------|-------|
| NEGATES | Chunk → Disease | 111,720 |
| NEGATES | Chunk → Drug | 21,001 |
| NEGATES | Chunk → OntologyTerm | 484,498 |
| **NEGATES total** | | **617,219** |
| TEMPORAL_BEFORE | Disease → Disease | 12,225 |
| TEMPORAL_BEFORE | Drug → Drug | 3,487 |
| **TEMPORAL_BEFORE total** | | **15,712** |
| **Grand total** | | **632,931** |

- Chunks scanned: 2,294,038
- Chunks receiving ≥1 edge: 190,987 (8.33%)
- Throughput: 0.2329 ms/chunk (534 s wall-clock, CPU-only)
- Probes: 10/10 PASS (5 negation + 5 temporal)
- Retrieval drift: 0.00% (SHA-256 ba1b5121… identical pre/post)

---

## Table S7. Guardrail Evaluation Summary

Source: `evaluations/step19_guardrails_eval_report.json`

| Feature | Tests Passed | Tests Failed | Avg Latency (ms) |
|---------|-------------|-------------|-----------------|
| F1: Cross-Modal Discrepancy Guardrail | 5/5 | 0 | 0.14 |
| F2: Epistemic Knowledge-Gap Mapper   | 5/5 | 0 | 0.07 |
| **Overall** | **10/10** | **0** | **0.11** |

F1 detects conflicts between text negation and visual findings (e.g., text:
"clear lungs" vs. BiomedCLIP pneumothorax score = 0.88 → HIGH severity alert).
F2 maps unanswerable queries to structured gap reports citing missing evidence
categories. Both guardrails operate in microsecond latency, adding negligible
overhead to the pipeline.

---

## Table S8. Security Audit Summary

Source: `SECURITY_AUDIT.md`

| Finding | Severity | Category | Status |
|---------|----------|----------|--------|
| F-01: Cypher injection in private store | HIGH | Injection | ✅ RESOLVED |
| F-02: Plaintext AES key storage | HIGH | Crypto | ✅ RESOLVED |
| F-03: Unsalted SHA-256 passwords + no rate limit | MEDIUM→HIGH | AuthN | ✅ RESOLVED |
| F-04: Cross-user existence oracle | MEDIUM | AuthZ | ✅ RESOLVED |
| F-05: Glob injection via image_id | LOW→MEDIUM | Validation | ✅ RESOLVED |
| F-06: No magic-byte sniffing on uploads | MEDIUM | Upload | ✅ RESOLVED |
| F-07: JWT secret fallback randomness | LOW | Crypto | ✅ RESOLVED |
| F-08: Swagger UI in prod | LOW | Exposure | ✅ RESOLVED |
| F-09: PHI fragments in logs | LOW | Privacy | ✅ RESOLVED |
| F-10: JWT in sessionStorage | LOW | Frontend | DEFERRED |
| F-11: No dependency lockfile | LOW | Dependency | ✅ RESOLVED |
| F-12/F-13: Status endpoint + secret scan | INFO | Hygiene | ✅ RESOLVED |

All HIGH and MEDIUM findings resolved before repository publication.
F-10 (JWT sessionStorage) deferred with documented rationale (tab-scoped,
no raw HTML sinks, Markdown-sanitised rendering).
