# Step 12 Part 3 & 4 — MedGraphRAG Conference Paper Tables & Evaluation Summary

This document presents the final paper-ready tables and formal evaluation summary for MedGraphRAG ($N=50$, seed 42 on MedQA US benchmark).

---

## 📊 Table 1: Main Evaluation & Ablation Results (MedQA US N=50)

| Config ID | Config Name | Graph Traversal | Verification Agent | Accuracy (All) | Accuracy (Answered) | Answered Rate | Hedged Rate | Refusal Rate | Wrong Assertion Rate | Median Latency |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **C1** | `C1_FULL` | ✅ ON | ✅ ON | **6.00%** | **33.33%** | **18.00%** | **0.00%** | **82.00%** | **12.00%** | **15386.05 ms** |
| **C2** | `C2_VECTOR_ONLY` | ❌ OFF | ✅ ON | **6.00%** | **50.00%** | **12.00%** | **0.00%** | **88.00%** | **6.00%** | **8767.87 ms** |
| **C3** | `C3_NO_VERIFY` | ✅ ON | ❌ OFF | **50.00%** | **51.02%** | **98.00%** | **0.00%** | **2.00%** | **48.00%** | **7702.43 ms** |
| **C4** | `C4_BASELINE` | ❌ OFF | ❌ OFF | **54.00%** | **55.10%** | **98.00%** | **0.00%** | **2.00%** | **44.00%** | **2717.68 ms** |

---

## 📈 Table 2: Provenance & Retrieval Metrics

| Config ID | Config Name | Avg Citations / Answer | Contamination Excluded Chunks | LLM Judge Fallback Calls |
| :---: | :--- | :---: | :---: | :---: |
| **C1** | `C1_FULL` | **9.78** | **26** | **0** |
| **C2** | `C2_VECTOR_ONLY` | **9.18** | **26** | **0** |
| **C3** | `C3_NO_VERIFY` | **9.78** | **26** | **0** |
| **C4** | `C4_BASELINE` | **9.18** | **26** | **0** |

---

## 🌐 Table 3: Graph Traversal Provenance & Entity Seeding

- **Positive Probes Reaching Graph Entities**: `7/10 (Target >= 7/10)`
- **Verified Query-Relevant Graph Paths**:

```text
[P01] Query: "warfarin INR monitoring guidelines atrial fibrillation"
     Path: Disease(Embolism) -[HAS_CHUNK]-> Document(Research_papers/PubMed/Abstracts/Pulmonary_Embolism/PMID_38823454) -[HAS_CHUNK]-> Chunk(Research_papers/PubMed/Abstracts/Pulmonary_Embolism/PMID_38823454__c1)

[P01] Query: "warfarin INR monitoring guidelines atrial fibrillation"
     Path: Disease(Atrial Fibrillation) -[DOCUMENT_MENTIONS]-> Document(Research_papers/PubMed/Abstracts/Atrial_Fibrillation/PMID_36356656) -[HAS_CHUNK]-> Chunk(Research_papers/PubMed/Abstracts/Atrial_Fibrillation/PMID_36356656__abs)

[P02] Query: "ACE inhibitor hypertension treatment first line"
     Path: Document(Clinical_practice_guidlines/Nice_guidlines/hypertension-in-adults-diagnosis-and-management-pdf-66141722710213) -[HAS_CHUNK]-> Chunk(Clinical_practice_guidlines/Nice_guidlines/hypertension-in-adults-diagnosis-and-management-pdf-66141722710213__c1)

[P02] Query: "ACE inhibitor hypertension treatment first line"
     Path: Document(Clinical_practice_guidlines/Who_IRIS/9789240033986-eng) -[HAS_CHUNK]-> Chunk(Clinical_practice_guidlines/Who_IRIS/9789240033986-eng__c5)

[P03] Query: "critical hemoglobin levels anemia transfusion threshold"
     Path: Document(Lab_rev_data/Consolidated_Lab_Critical_Values_Dataset_CLEANED) -[HAS_CHUNK]-> Chunk(Lab_rev_data/Consolidated_Lab_Critical_Values_Dataset_CLEANED__row3)

```

---

## 💻 Table 4: Server Hardware & System Resource Footprint

| Resource Metric | Measured Value | Budget Limit | Status |
| :--- | :---: | :---: | :---: |
| **System Peak RAM** | **3.62 GB** | $\le 12.0$ GB | ✅ PASS |
| **GPU Peak VRAM** | **4784 MB** | $\le 5,500$ MB | ✅ PASS |
| **FAISS IVFpq Memory** | **240 MB** | CPU Memory | ✅ PASS |
| **Kùzu Graph Memory** | **180 MB** | CPU mmap | ✅ PASS |
| **LLM Concurrent Instances** | **1** | 1 (Serialized) | ✅ PASS |

---

## 🔒 Verification & Index Integrity Proofs

1. **Contamination Guard Status**: ✅ **ACTIVE & PROVEN** (Excluded 26 MedQA question chunks per config run).
2. **Flag Restoration Check**: ✅ **PASSED** (`retrieval_graph_enabled=True`, `pipeline_verification_enabled=True`, P01 fused score = `0.1774`).
3. **Global Index Byte Integrity**: ✅ **UNTOUCHED** (FAISS: `2,294,038` vectors, Kùzu: `2,499,528` nodes).
