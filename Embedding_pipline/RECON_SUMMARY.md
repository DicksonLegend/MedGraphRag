# MedGraphRAG — Recon Summary & Project Handover Document
**Date**: August 4, 2026
**Schema Version**: 1.2
**Hardware Context**: NVIDIA RTX 3050 Laptop GPU (6 GB VRAM) / 16 GB System RAM
**Status**: STEP 0 (Recon) Completed & Updated with UMLS Terminology Layer. Ready to proceed with STEP 1 (Embedding Pipeline).

---

## 1. Executive Summary & Core Rules
MedGraphRAG is an offline, privacy-preserving AI healthcare assistant designed for consumer laptop hardware.

### Key Architectural Choices (FROZEN)
- **Retrieval**: Hybrid FAISS (dense vector) + Kùzu (embedded graph DB), fused at retrieval.
- **Embedded Graph DB**: Kùzu (in-process, columnar, Cypher-subset, Python package `kuzu`).
- **Embedding Model**: MedCPT (`ncbi/MedCPT-Article-Encoder` for docs/chunks, `ncbi/MedCPT-Query-Encoder` for queries).
- **UMLS Terminology Layer**: ~11 GB JSON parsed in `Datasets/Medical_ontologies/`. Strictly **GRAPH-ONLY** (never FAISS). Streamed line-by-line (never full load in RAM). Filtered at graph build to ~110 target diseases + related CUIs & semantic types (Disease, Drug, Symptom, Procedure, Laboratory).
- **Isolated Knowledge Spaces**:
  - `GLOBAL`: Read-only, built offline from curated datasets.
  - `USER PRIVATE`: Runtime isolated per user (`private_store/<user_id>/`), AES-encrypted at rest, never merged into global.
- **Hardware Constraints**: 6 GB VRAM ceiling (bulk GPU embed permitted with memory checks `free > 1.5 GB`, CPU fallback available); 16 GB system RAM ceiling (stream JSONL line-by-line, incremental FAISS builds, metadata sidecar on disk).

---

## 2. Codebase Map ("What Already Exists")

### A. Data Normalization Module (`/home/dicksone/Documents/MedGraphRag/Data_Normalization`)
- **Status**: **100% Complete & Operational**
- **Files**: `run.py`, `pipeline.py`, `config.py`, `schema.py`, `utils.py`, `parsers/` (20 parsers).
- **Capabilities**:
  - Converts 12 biomedical datasets into standardized Schema v1.2 JSON documents.
  - PyMuPDF default parser for clean PDFs with Docling CUDA fallback for scanned/complex PDFs.
  - SHA-256 deduplication pre-scan (`duplicate_map.json`).
  - Memory-safe stream processing & output capping (prevents OOM).
  - Incremental CSV logging (`processing_log.csv`) and failed file logging (`failed_files.jsonl`).

### B. Embedding & Graph Pipeline (`/home/dicksone/Documents/MedGraphRag/Embedding_pipline`)
- **Status**: **Empty (To be built next)**
- **Required Components for Implementation Phase**:
  1. **Chunking Engine**: Medical/semantic chunking with provenance metadata hanging off Document nodes.
  2. **Embedder Interface**: MedCPT encoders (`MedCPT-Article-Encoder` & `MedCPT-Query-Encoder`).
  3. **FAISS Vector Store Builder**: Incremental batch indexing with on-disk metadata sidecar.
  4. **Kùzu Graph Store Builder**: Document, Chunk, and Entity node tables; relational & provenance edge tables.
  5. **Unified Parameterized Builder**: `build_knowledge_base(destination: Path)` handling both `GLOBAL` and `USER PRIVATE` paths.
  6. **Target Router**: Enforces Category -> Target rules & `structured_data` overrides.

---

## 3. Data Breakdown & Verification Audit

### A. Document Counts by Category (`Datasets/normalized`)
Total Normalized JSON Documents: **15,531** (100% Schema v1.2)

| Category | Document Count | Non-Empty `structured_data` Files |
| :--- | :--- | :--- |
| `guideline` | 7,992 | 2 |
| `research_paper` | 7,334 | 2 |
| `lab_reference` | 70 | 47 |
| `ontology` | 54 | 0 |
| `textbook` | 49 | 30 |
| `drug` | 20 | 17 |
| `qa_benchmark` | 7 | 6 |
| `disease` | 2 | 0 |
| `clinical_reference` | 2 | 0 |
| `evidence_qa` | 1 | 0 |
| **Total** | **15,531** | **104** |

### B. Content Deduplication Audit
- **8 unique content hash groups** identified.
- **64 total duplicate file entries** logged in `duplicate_map.json`.

### C. Resolved Target Distribution (Computed via Routing Rules)
Routing Rules:
- `guideline` $\rightarrow$ both
- `clinical_reference` $\rightarrow$ faiss (graph if structured_data non-empty)
- `disease` $\rightarrow$ both
- `drug` $\rightarrow$ both
- `lab_reference` $\rightarrow$ graph (faiss too if prose > 200 chars)
- `ontology` $\rightarrow$ graph (NEVER faiss)
- `textbook` $\rightarrow$ faiss
- `research_paper` $\rightarrow$ faiss
- `evidence_qa` $\rightarrow$ faiss
- `qa_benchmark` $\rightarrow$ none (EXCLUDED to prevent benchmark contamination)
- **Override Rule**: Non-empty `structured_data` forces `graph` into target.

**Results**:
- **`both` (FAISS + Kùzu)**: 8,116 documents (52.26%)
- **`faiss`**: 7,354 documents (47.35%)
- **`graph` (Kùzu only)**: 54 documents (0.35%)
- **`none` (Excluded)**: 7 documents (0.05%)

### D. UMLS Terminology Layer Integration
- **Parsed Location**: `Datasets/Medical_ontologies/` (~11 GB JSON files).
- **Files Parsed**: `MRCONSO`, `MRREL`, `MRSTY`, `MRDEF`, `MRHIER`, `MRRANK`, `MRSAB`, `SPECIALIST` Lexicon, Semantic Network.
- **Role Breakdown**:
  - `MRCONSO`: Concept nodes & synonym mappings.
  - `MRREL`: Relational edges between CUIs.
  - `MRSTY`: Semantic types (Disease, Drug, Symptom, Procedure, Laboratory).
  - `MRHIER`: Taxonomic hierarchy edges.
  - `SPECIALIST`: Query-time synonym & abbreviation expansion ONLY (not loaded into graph database).
- **Mandatory Constraints**:
  1. **Graph-Only**: Never embedded into FAISS.
  2. **Memory Safety**: Never load 11 GB into RAM — stream line-by-line / in chunks.
  3. **Target Filtering**: At Kùzu build time, filter UMLS to the ~110 target project diseases + related CUIs & semantic types (do NOT load entire UMLS database).

---

## 4. Environment & Dependency Status

### Environment: `/home/dicksone/Documents/MedGraphRag/Data_Normalization/.venv`
- `torch`: `2.6.0+cu124` (Installed)
- `fitz` (PyMuPDF): `1.28.0` (Installed)
- `docling`: `Installed`
- `charset-normalizer`: `3.4.9` (Installed)

### Packages to Install for Next Phase:
- `sentence-transformers`
- `faiss-cpu` / `faiss-gpu`
- `kuzu`
- `spacy` / `scispacy` (optional for NER)

---

## 5. Next Steps when Resuming
1. Confirm explicit approval ("proceed") to start writing pipeline code.
2. Install required packages (`sentence-transformers`, `faiss-cpu`, `kuzu`) into the Python environment.
3. Build the `/Embedding_pipline` modules following the frozen architectural constraints.
