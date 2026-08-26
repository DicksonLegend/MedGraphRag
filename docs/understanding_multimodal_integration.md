# MedGraphRAG Multimodal Architecture & Frontend Integration Understanding Report

**Date**: 2026-08-26  
**Scope**: Read-only structural audit of multimodal artifacts, backend services, and frontend integration state.

---

## A. Artifact & Component Inventory

| Component / Artifact | File Path | Status | Purpose |
| :--- | :--- | :---: | :--- |
| **Download Manifest** | `data/multimodal/MANIFEST.md` | **COMPLETE** | Tracks source URLs, SHA-256 hashes, licenses, and byte sizes for all 7 multimodal datasets/models (OpenI, VQA-RAD, SLAKE, BiomedCLIP, Qwen2-VL, IU-Xray sample100). |
| **OpenI Radiology Chunks** | `data/multimodal/chunks/openi_chunks.jsonl` | **COMPLETE** | 11,211 normalized text chunks from 3,955 OpenI radiology reports with linked `image_ids` (SHA: `b60730ca`). |
| **BiomedCLIP Visual Findings** | `data/multimodal/visual_findings_v2.json` | **COMPLETE** | Zero-shot visual finding probabilities across 14 CheXzero pathology classes for 315 VQA-RAD and 100 OpenI images (Mean AUC: 0.680 > 0.65 gate, SHA: `67f169e6`). |
| **Multimodal Report Graph** | `data/multimodal/report_graph/kuzu.db` | **COMPLETE** | Standalone Kùzu database containing `Image` (315), `VisualFinding` (4,410), and `Report` (11,211) nodes with `IMAGE_SHOWS` (5,810), `REPORT_DESCRIBES` (48), and `FINDING_NEGATES` (321) edges. Isolated from global `kuzu_db_v5`. |
| **Crosslink Report** | `data/multimodal/report_graph/crosslink_report.json` | **COMPLETE** | Metadata documenting cross-link edge construction between OpenI reports and CXR sample images. |
| **VLM Image Eval Report** | `evaluations/multimodal/step16_image_report.json` | **COMPLETE** | Evaluation results of Qwen2-VL-2B (CPU-mode) across 20 VQA-RAD samples (Exact Match token overlap: 0.35, Mean latency: 11.47s, Peak RSS: 2.68 GB, SHA: `3bede101`). |
| **Adjudicated IR Metrics** | `evaluations/multimodal/step17_ir_metrics_v2.json` | **COMPLETE** | User-adjudicated IR metrics (P@5: 0.18, R@5: 0.54, MRR: 0.353, nDCG@10: 0.377, SHA: `8a2b8fec`). |
| **SLAKE VQA Evaluation** | `evaluations/multimodal/slake_vqa_eval.json` | **COMPLETE** | Multimodal question answering evaluation on the SLAKE medical dataset. |
| **Multimodal VLM Device Policy** | `backend/app/multimodal/device.py` | **COMPLETE** | Hardware isolation layer enforcing `resolve_vlm_device() -> 'cpu'` to guarantee 100% of the 6GB VRAM on RTX 3050 is reserved for the primary Qwen2.5-7B LLM. |
| **Multimodal Schemas** | `backend/app/multimodal/schemas.py` | **COMPLETE** | Pydantic contracts for `MedicalImage`, `ImageModality`, `ImageOrientation`, `ImageAnalysisResult`, `PDFDocument`, `PDFPage`, `PDFImage`, and `MultimodalIngestionResult`. |
| **Multimodal Service Layer** | `backend/app/multimodal/service.py` | **HALF-CREATED** | High-level orchestrator. File ingestion, DICOM/PDF loading, and single image pipelines are implemented, but full report pipeline bridging and retrieval vector indexing are stubs (`"not_implemented"`). |
| **Multimodal Parser** | `backend/app/multimodal/parser.py` | **HALF-CREATED** | Implements DICOM reading (`pydicom`), image modality/orientation heuristics, and PyMuPDF embedded image extraction. However, `analyze_medical_image_with_vlm()` (lines 301–355) is currently a **STUB** returning placeholder mock findings rather than invoking the Qwen2-VL model from `vlm_image_report.py`. |
| **FastAPI Multimodal Routes** | `backend/app/multimodal/routes.py` | **COMPLETE** | API router exposing `/multimodal/ingest`, `/multimodal/analyze-image`, `/multimodal/parse-pdf`, and `/multimodal/status`. |
| **API Route Forwarder** | `backend/app/api/routes/multimodal.py` | **COMPLETE** | Mounts multimodal router into the FastAPI application under the `/multimodal` prefix. |
| **Frontend Multimodal UI** | `frontend/src/...` | **MISSING** | No UI components, no scan-upload widget, no radiology report viewer, and no `multimodalApi` client exists in the frontend. |

---

## B. Backend Endpoint Map

### 1. `GET /multimodal/status`
- **Method**: `GET`
- **Auth**: None (Public)
- **Request**: None
- **Response Schema**:
  ```json
  {
    "service": "multimodal",
    "version": "0.1.0",
    "capabilities": {
      "image_formats": ["png", "jpg", "jpeg", "tiff", "bmp", "webp"],
      "dicom_support": false,
      "pdf_support": true,
      "vlm_analysis": false,
      "vlm_model": "Not configured",
      "ocr_support": true,
      "embedded_image_analysis": false
    },
    "supported_modalities": ["xray", "ct", "mri", "ultrasound", "pathology", "dermatology", "oct", "fundus", "endoscopy", "unknown"]
  }
  ```
- **Dependencies**: None.
- **Wired / Tested**: **WIRED & TESTED** (Returns HTTP 200).
- **Missing for Production**: Dynamic capability flags based on installed libraries and configured weights.

---

### 2. `POST /multimodal/analyze-image`
- **Method**: `POST` (Multipart Form Data)
- **Auth**: Required (`Bearer JWT` via `get_current_user`)
- **Request Parameters**:
  - `file`: `UploadFile` (Required: PNG, JPG, JPEG, TIFF, BMP, WebP)
  - `custom_prompt`: `Optional[str]` (Form field)
- **Response Schema (`ImageAnalyzeResponse`)**:
  ```json
  {
    "image_id": "string",
    "findings": ["string"],
    "findings_detailed": [{"finding": "string", "location": "string", "severity": "string", "confidence": 0.0}],
    "impression": "string",
    "recommendations": ["string"],
    "confidence_scores": {"finding_name": 0.85},
    "modality": "xray",
    "processing_time_ms": 1240.5,
    "model_used": "Qwen2-VL-2B / BiomedCLIP",
    "provenance": ["string"]
  }
  ```
- **Dependencies**: `PIL`, `pydicom` (optional), `backend/app/multimodal/parser.py`, `Qwen2-VL-2B-Instruct-Q4_K_M.gguf` + `mmproj`, `biomedclip-hf`.
- **Wired / Tested**: **WIRED BUT CALLS STUB** (`analyze_medical_image_with_vlm()` in `parser.py` currently returns hardcoded mock findings instead of running Qwen2-VL or BiomedCLIP).
- **Missing for Production**: Connect `analyze_medical_image_with_vlm()` in `parser.py` to the working Qwen2-VL CPU pipeline from `scripts/multimodal/vlm_image_report.py` and BiomedCLIP zero-shot scorer from `scripts/multimodal/chexzero_encode_v2.py`.

---

### 3. `POST /multimodal/ingest`
- **Method**: `POST` (Multipart Form Data)
- **Auth**: Required (`Bearer JWT` via `get_current_user`)
- **Request Parameters**:
  - `files`: `List[UploadFile]` (Batch of images/PDFs)
  - `user_id`: `Optional[str]`
  - `destination`: `str` (Default: `"private"`)
  - `analyze_images`: `bool` (Default: `true`)
  - `run_full_interpretation`: `bool` (Default: `true`)
- **Response Schema (`MultimodalIngestResponse`)**:
  - `ingestion_id`: `str`
  - `images_processed`: `int`
  - `pdfs_processed`: `int`
  - `total_findings`: `int`
  - `total_latency_ms`: `float`
  - `image_results`: `List[ImageAnalysisResult]`
  - `pdf_results`: `List[PDFDocument]`
  - `errors`: `List[Dict[str, str]]`
  - `provenance`: `List[str]`
  - `interpretation`: `Optional[Dict[str, Any]]`
- **Dependencies**: `PyMuPDF`, `PIL`, `MultimodalService`.
- **Wired / Tested**: **WIRED**.
- **Missing for Production**: Needs live VLM binding and integration with private AES-256-GCM storage.

---

### 4. `POST /multimodal/parse-pdf`
- **Method**: `POST` (Multipart Form Data)
- **Auth**: Required (`Bearer JWT` via `get_current_user`)
- **Request Parameters**:
  - `file`: `UploadFile` (PDF)
  - `analyze_embedded_images`: `bool` (Default: `true`)
- **Response Schema (`PDFParseResponse`)**:
  - `document_id`, `filename`, `file_bytes_hash`, `page_count`, `full_text`, `pages` (with extracted tables and embedded image analyses), `needs_review`.
- **Dependencies**: `PyMuPDF (fitz)`, `PIL`.
- **Wired / Tested**: **WIRED**.
- **Missing for Production**: Live VLM extraction on embedded image slices.

---

## C. Frontend Gap Analysis

### 1. Existing Frontend Pages & Roles
1. **Clinical Query Console (`/chat`)**: Multi-hop GraphRAG query interface with confidence badges, latency breakdown, graph traversal path view, and evidence cards.
2. **Diagnostic Reports (`/reports`)**: Lab report upload vault (PDF/XLSX/CSV/OCR), parsing tabular blood chemistry/hematology results, normal/critical range assessment, and AES-256-GCM encrypted private store.
3. **MedTrend Analytics (`/trends`)**: Longitudinal biomarker tracking over time.
4. **CareGap Reconcile (`/caregap`)**: Guideline disparity auditing.
5. **Evidence Coverage Map (`/coverage`)**: Entity density decomposition matrix.
6. **Admin Audit Console (`/admin`)**: System management and metrics.

### 2. Architecture Fit: Dedicated Page vs. ReportsPage Extension
- **Recommendation**: **Dual Integration Strategy**:
  1. **Primary Hub**: Extend the existing **Diagnostic Reports (`/reports`)** page with a top-level tab switcher:
     - **Tab 1: Laboratory Chemistry & Biomarkers** (Existing lab report upload, table extraction, range assessment).
     - **Tab 2: Medical Imaging & Scans (CXR / CT / MRI)** (New multimodal scan uploader, modality detection badge, visual finding confidence sliders, and radiology impression viewer).
  2. **Query Console Integration (`/chat`)**: Add an **"Attach Scan"** button in the chat input prompt bar allowing clinicians to upload an X-ray alongside a clinical query (e.g., *"Does this CXR show signs of heart failure?"*).

### 3. Reusable Frontend Components
- **`SubwayMap.tsx`**: Reusable for visual progression steps (Upload → Modality Detection → VLM Finding Extraction → Knowledge Graph Corroboration).
- **`CriticalEscalationBanner.tsx`**: Reusable for urgent visual findings (e.g., Tension Pneumothorax, Acute Massive Effusion).
- **`EcgLoader.tsx`**: Reusable loading spinner with clinical heart rhythm animation during VLM inference.
- **`EvidenceCard.tsx` / `MarkdownAnswer.tsx`**: Reusable for displaying structured findings, impressions, and recommendations.

### 4. Missing Frontend Pieces
- **API Client**: Create `frontend/src/api/multimodal.ts` with typed methods for `analyzeImage()`, `ingestMultimodal()`, `parsePdf()`, and `getStatus()`.
- **Types**: Add TypeScript interfaces for `ImageAnalysisResult`, `VisualFinding`, `ImageModality`, and `MultimodalIngestResponse` in `frontend/src/api/types.ts`.
- **UI Components**:
  - `ScanUploadDropzone.tsx`: Drag-and-drop supporting PNG, JPG, DICOM with image thumbnail preview.
  - `ScanViewer.tsx`: High-resolution canvas/image viewer with zoom, pan, and inversion toggle for radiology review.
  - `VisualFindingsCard.tsx`: Structured findings breakdown with confidence bars, anatomical locations, and CheXzero/BiomedCLIP score indicators.
  - `RadiologyReportDrawer.tsx`: Detailed side drawer showing full impression, follow-up recommendations, and linked graph nodes from `report_graph/kuzu.db`.

---

## D. Resource & Constraint Notes

### 1. Hardware & VRAM Allocation (RTX 3050 6 GB)
- **Primary LLM (Qwen2.5-7B-Instruct Q4_K_M)**: Allocates **4,764 MiB (~4.8 GB)** VRAM on the NVIDIA GeForce RTX 3050 Laptop GPU (leaving ~1.38 GB free headroom).
- **VLM Hardware Isolation Policy**:
  - `backend/app/multimodal/device.py` strictly mandates:
    ```python
    def resolve_vlm_device() -> str:
        return "cpu"
    ```
  - `Qwen2-VL-2B-Instruct-Q4_K_M.gguf` (986 MB) + `mmproj` runs entirely on **CPU** with `n_gpu_layers=0` and `n_threads=4`.
  - Peak RSS during Qwen2-VL vision inference is **~2.68 GB RAM**, well within the system's 16 GB available RAM.
  - **No VRAM collisions**: Because the VLM is pinned to CPU, it can execute concurrently without interrupting or evicting the GPU-resident 7B LLM.

### 2. Privacy & Data Isolation Rules
- User-uploaded scan images and extracted findings must follow the same AES-256-GCM private storage model as lab reports.
- Storage destination must enforce strict user isolation: `private_store/{user_id}/scans/`.
- Uploaded scans must never leak into the global index (`index/global/kuzu_db_v5` remains strictly read-only).

---

## E. Ordered Frontend Integration Roadmap (No Code Yet)

```
Step 1: TypeScript Contract Definitions
  └── Add Multimodal API request/response types in frontend/src/api/types.ts.

Step 2: API Client Implementation
  └── Create frontend/src/api/multimodal.ts wrapping /multimodal/analyze-image and /multimodal/status.

Step 3: Backend VLM Engine Hookup
  └── Connect analyze_medical_image_with_vlm() in backend/app/multimodal/parser.py to Qwen2-VL-2B CPU loader.

Step 4: Scan Upload & Viewer Components
  ├── Create ScanUploadDropzone.tsx (drag-and-drop with image preview & DICOM handling).
  ├── Create VisualFindingsCard.tsx (probability bars for 14 CheXzero pathologies).
  └── Create RadiologyReportDrawer.tsx (clinical impression & recommendation breakdown).

Step 5: ReportsPage Tabbed Extension
  └── Update frontend/src/pages/ReportsPage.tsx with "Lab Reports" and "Medical Scans" tabs.

Step 6: Chat Console Multimodal Attachment
  └── Add scan attachment button to ClinicalAnswerConsole.tsx for image-guided QA.

Step 7: End-to-End User Verification & Testing
  └── Upload sample CXR (e.g. CXR1000_IM-0003_0.png) in the UI and verify latency (<12s) and finding fidelity.
```

---

## F. Risks & Open Questions

1. **DICOM Browser Rendering**:
   - Standard browser `<img>` tags cannot render raw `.dcm` files.
   - *Question*: Should the backend auto-convert `.dcm` to `.png` preview bytes in the API response, or should we use a client-side WebAssembly DICOM parser (e.g., Cornerstone.js)? *(Recommended: Backend auto-conversion to 8-bit PNG preview for simplicity).*

2. **Zero-Shot Classifier vs. Generative VLM Priority**:
   - OpenCode built two distinct inference pipelines:
     1. `chexzero_encode_v2.py` (BiomedCLIP: fast zero-shot probability scores across 14 pathologies, ~200ms).
     2. `vlm_image_report.py` (Qwen2-VL-2B: slow generative natural-language impression & VQA, ~11.5s on CPU).
   - *Question*: Should the UI display both (BiomedCLIP visual findings bar chart + Qwen2-VL written impression), or allow the clinician to toggle between Fast Triage vs. Full Generative Interpretation?

3. **Report Graph Entity Linking**:
   - `data/multimodal/report_graph/kuzu.db` has 48 cross-linked OpenI study graphs linking `Image -> VisualFinding -> Report`.
   - *Question*: Do you want the UI scan viewer to highlight linked graph paths when a user uploads a known sample image or references an OpenI study ID?
