# Step 12 Part 2.5 — MedQA US N=50 Benchmark & Ablation Report (Corrected Metrics)

This report details the exact performance of MedGraphRAG across 4 ablation configurations evaluated on MedQA US ($N=50$, seed 42) with strict contamination filtering and verified metric rules.

---

## 📊 1. Corrected 4-Config Ablation Matrix

| Config ID | Config Name | Graph Traversal | Verification Agent | Accuracy (All) | Accuracy (Answered) | Answered Rate | Hedged Rate | Refusal Rate | Wrong Assertion Rate | Median Latency (ms) |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **C1** | `C1_FULL` | ✅ ON | ✅ ON | **6.00%** | **33.33%** | **18.00%** | **0.00%** | **82.00%** | **12.00%** | **15386.05 ms** |
| **C2** | `C2_VECTOR_ONLY` | ❌ OFF | ✅ ON | **6.00%** | **50.00%** | **12.00%** | **0.00%** | **88.00%** | **6.00%** | **8767.87 ms** |
| **C3** | `C3_NO_VERIFY` | ✅ ON | ❌ OFF | **50.00%** | **51.02%** | **98.00%** | **0.00%** | **2.00%** | **48.00%** | **7702.43 ms** |
| **C4** | `C4_BASELINE` | ❌ OFF | ❌ OFF | **54.00%** | **55.10%** | **98.00%** | **0.00%** | **2.00%** | **44.00%** | **2717.68 ms** |

---

## 🛡️ 2. Contamination Guard Filter Proof

- **Blocked Prefixes**: `["Medical_books/MedQA/questions/", "MedQA/questions/"]`
- **Filter Proof Test Query**: `A 43-year-old man comes to the physician because of redness and swelling of his ...`
- **Raw Chunks Count**: `11`
- **Excluded Question Chunks**: `2`
- **Excluded Chunk IDs**: `['Medical_books/MedQA/questions/US/US_qbank__c4628', 'Medical_books/MedQA/questions/US/train__c200']`
- **Filter Proof Status**: ✅ **PASSED**

---

## 🔄 3. Post-Benchmark Flag Restoration & 1c Regression Check

- **`settings.retrieval_graph_enabled`**: `True` (Restored)
- **`settings.pipeline_verification_enabled`**: `True` (Restored)
- **P01 Retrieval Top Doc**: `Research_papers/PubMed/Abstracts/Pulmonary_Embolism/PMID_38823454`
- **P01 Top Fused Score**: `0.1774` (Expected `0.1774` $\pm 0.01$)
- **P01 Items Count**: `9`
- **Restoration Check**: ✅ **PASSED** (`restoration_passed: true`)

---

## 🔒 4. Global Index Integrity Verification

- **FAISS Vector Count**: `2,294,038` vectors (Untouched)
- **Kùzu Graph Nodes**: `2,499,528` nodes (Untouched)

---

## 🔬 5. Detailed Metric Definitions & Fixed Rules

1. **Answered**: `extracted in ('A', 'B', 'C', 'D')`
2. **Refused**: `extracted == "refused_or_unanswered"`
3. **Hedged**: `is_answered AND answer_text_contains_refusal_phrasing`
4. **Accuracy (All)**: `(correct_count / 50) * 100`
5. **Accuracy (Answered)**: `(correct_count / answered_count) * 100` if `answered > 0` else `0.0`
6. **Wrong Assertion Rate**: `((answered_count - correct_count) / 50) * 100`
