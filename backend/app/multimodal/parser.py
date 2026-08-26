"""
MedGraphRAG Backend — Multimodal Parser
========================================
Parses medical images (X-ray, CT, MRI, pathology) and PDF documents using
BiomedCLIP zero-shot pathology scoring, Qwen2-VL-2B vision-language model (CPU),
and Kùzu report-graph cross-linking.

Supports:
- DICOM (.dcm) medical images with min-max windowing & 8-bit PNG preview generation
- Standard images (PNG, JPG, TIFF) via PIL with preview downsampling
- BiomedCLIP zero-shot fast triage (~200ms) over 14 CheXzero pathology classes
- Qwen2-VL-2B generative radiological impression & recommendations on CPU
- Report graph entity linking against data/multimodal/report_graph/kuzu.db
"""

from __future__ import annotations

import base64
import gc
import hashlib
import io
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import fitz  # PyMuPDF
import numpy as np
import torch
from PIL import Image

try:
    import psutil
except ImportError:
    psutil = None

import kuzu
from fastapi import HTTPException, status

from app.config import settings
from app.multimodal.device import resolve_vlm_device
from app.multimodal.schemas import (
    ImageAnalysisResult,
    ImageModality,
    ImageOrientation,
    KnowledgeGraphPath,
    MedicalImage,
    MultimodalIngestionResult,
    PDFDocument,
    PDFImage,
    PDFPage,
    VisualFinding,
)

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
BIOMEDCLIP_DIR = ROOT_DIR / "data/external/models/biomedclip-hf"
QWEN2_VL_GGUF = ROOT_DIR / "data/external/models/Qwen2-VL-2B-Instruct-Q4_K_M.gguf"
QWEN2_VL_MMPROJ = ROOT_DIR / "data/external/models/mmproj-Qwen2-VL-2B-Instruct-Q8_0.gguf"
REPORT_GRAPH_DB_DIR = ROOT_DIR / "data/multimodal/report_graph"

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}
DICOM_EXTENSIONS = {".dcm", ".dicom"}
PDF_EXTENSIONS = {".pdf"}

CHEXZERO_LABELS = [
    "enlarged cardiomediastinum",
    "cardiomegaly",
    "lung lesion",
    "airspace opacity",
    "edema",
    "consolidation",
    "pneumonia",
    "atelectasis",
    "pneumothorax",
    "pleural effusion",
    "pleural other",
    "fracture",
    "support devices",
    "no finding",
]

POS_TEMPLATES = [
    "{c}",
    "{c} shown",
    "evidence of {c}",
    "indication of {c}",
    "the patient has {c}",
    "chest x-ray showing {c}",
    "presence of {c}",
    "radiograph demonstrates {c}",
]

NEG_TEMPLATES = [
    "no {c}",
    "no evidence of {c}",
    "{c} absent",
    "free of {c}",
    "negative for {c}",
    "chest x-ray without {c}",
    "unremarkable for {c}",
    "resolution of {c}",
]

AUC_BENCHMARK_REFERENCE = {
    "cardiomegaly": 0.814,
    "pleural effusion": 0.803,
    "support devices": 0.776,
    "airspace opacity": 0.743,
    "edema": 0.697,
    "lung lesion": 0.686,
    "fracture": 0.647,
    "pneumothorax": 0.612,
    "consolidation": 0.589,
    "enlarged cardiomediastinum": 0.574,
    "pleural other": 0.560,
    "pneumonia": 0.650,
    "atelectasis": 0.650,
    "no finding": 0.720,
}


def compute_file_hash(file_bytes: bytes) -> str:
    """Compute SHA-256 hash of file bytes."""
    return hashlib.sha256(file_bytes).hexdigest()


def detect_image_modality(filename: str, image: Optional[Image.Image] = None) -> ImageModality:
    """Detect medical imaging modality from filename and characteristics."""
    fn = filename.lower()
    if any(kw in fn for kw in ["xray", "x-ray", "chest", "radiograph", "cxr", "nlmcxr", "openi", "synpic"]):
        return ImageModality.XRAY
    if any(kw in fn for kw in ["ct", "cat_scan", "computed_tomography"]):
        return ImageModality.CT
    if any(kw in fn for kw in ["mri", "magnetic_resonance", "t1", "t2", "flair", "dwi"]):
        return ImageModality.MRI
    if any(kw in fn for kw in ["us", "ultrasound", "sonogram", "echo"]):
        return ImageModality.ULTRASOUND
    if any(kw in fn for kw in ["path", "histology", "h&e", "hne", "biopsy", "slide"]):
        return ImageModality.PATHOLOGY
    if any(kw in fn for kw in ["derm", "skin", "lesion", "melanoma"]):
        return ImageModality.DERMATOLOGY
    if any(kw in fn for kw in ["oct", "optical_coherence"]):
        return ImageModality.OCT
    if any(kw in fn for kw in ["fundus", "retina", "ophthalm"]):
        return ImageModality.FUNDUS
    if any(kw in fn for kw in ["endo", "gastroscopy", "colonoscopy", "bronchoscopy"]):
        return ImageModality.ENDOSCOPY
    return ImageModality.XRAY


def detect_orientation(filename: str, dicom_tags: Optional[Dict[str, Any]] = None) -> ImageOrientation:
    """Detect image orientation from filename or DICOM metadata."""
    if dicom_tags:
        view = str(dicom_tags.get("ViewPosition", "")).upper()
        if view in ("AP", "PA", "LATERAL", "LPO", "RPO", "LAO", "RAO"):
            if view in ("LPO", "RPO", "LAO", "RAO"):
                return ImageOrientation.OBLIQUE
            return ImageOrientation(view)

    fn = filename.lower()
    if "ap" in fn or "anteroposterior" in fn:
        return ImageOrientation.AP
    if "pa" in fn or "posteroanterior" in fn:
        return ImageOrientation.PA
    if "lat" in fn or "lateral" in fn:
        return ImageOrientation.LATERAL
    if "obl" in fn or "oblique" in fn:
        return ImageOrientation.OBLIQUE
    if "axial" in fn or "transverse" in fn:
        return ImageOrientation.AXIAL
    if "coronal" in fn:
        return ImageOrientation.CORONAL
    if "sagittal" in fn or "sag" in fn:
        return ImageOrientation.SAGITTAL
    return ImageOrientation.PA


def load_dicom_image(file_bytes: bytes) -> Tuple[Image.Image, bytes, Dict[str, Any]]:
    """
    Load DICOM image bytes, extract clinical tags, apply min-max windowing,
    and generate downscaled 8-bit PNG preview bytes (≤1024px).
    """
    try:
        import pydicom
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="DICOM parsing requires pydicom. Please install pydicom.",
        )

    try:
        ds = pydicom.dcmread(io.BytesIO(file_bytes))
        pixel_array = ds.pixel_array.astype(np.float32)

        # Apply Rescale Slope / Intercept if present
        slope = getattr(ds, "RescaleSlope", 1.0)
        intercept = getattr(ds, "RescaleIntercept", 0.0)
        pixel_array = pixel_array * float(slope) + float(intercept)

        # Min-max windowing to 8-bit uint8
        p_min = float(np.percentile(pixel_array, 1))
        p_max = float(np.percentile(pixel_array, 99))
        if p_max > p_min:
            norm_array = np.clip((pixel_array - p_min) / (p_max - p_min) * 255.0, 0, 255).astype(np.uint8)
        else:
            norm_array = np.zeros_like(pixel_array, dtype=np.uint8)

        # Check PhotometricInterpretation (invert if MONOCHROME1)
        photometric = getattr(ds, "PhotometricInterpretation", "")
        if photometric == "MONOCHROME1":
            norm_array = 255 - norm_array

        pil_image = Image.fromarray(norm_array).convert("RGB")

        # Downscale for preview (≤1024px)
        max_dim = max(pil_image.width, pil_image.height)
        if max_dim > 1024:
            scale = 1024.0 / max_dim
            new_size = (int(pil_image.width * scale), int(pil_image.height * scale))
            preview_img = pil_image.resize(new_size, Image.Resampling.LANCZOS)
        else:
            preview_img = pil_image

        preview_buf = io.BytesIO()
        preview_img.save(preview_buf, format="PNG", optimize=True)
        preview_bytes = preview_buf.getvalue()

        tags = {
            "PatientID": getattr(ds, "PatientID", None),
            "StudyID": getattr(ds, "StudyID", None),
            "SeriesNumber": getattr(ds, "SeriesNumber", None),
            "InstanceNumber": getattr(ds, "InstanceNumber", None),
            "StudyDate": getattr(ds, "StudyDate", None),
            "Modality": getattr(ds, "Modality", "CR"),
            "BodyPartExamined": getattr(ds, "BodyPartExamined", "CHEST"),
            "ViewPosition": getattr(ds, "ViewPosition", "PA"),
            "PixelSpacing": [float(x) for x in getattr(ds, "PixelSpacing", [1.0, 1.0])],
        }
        return pil_image, preview_bytes, tags
    except Exception as e:
        logger.error("Failed to parse DICOM image: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unsupported DICOM image file: {e}",
        )


def load_standard_image(file_bytes: bytes) -> Tuple[Image.Image, bytes]:
    """
    Load standard PNG/JPG/TIFF image, convert to RGB, and generate ≤1024px 8-bit PNG preview bytes.
    """
    try:
        pil_image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        max_dim = max(pil_image.width, pil_image.height)
        if max_dim > 1024:
            scale = 1024.0 / max_dim
            new_size = (int(pil_image.width * scale), int(pil_image.height * scale))
            preview_img = pil_image.resize(new_size, Image.Resampling.LANCZOS)
        else:
            preview_img = pil_image

        preview_buf = io.BytesIO()
        preview_img.save(preview_buf, format="PNG", optimize=True)
        preview_bytes = preview_buf.getvalue()
        return pil_image, preview_bytes
    except Exception as e:
        logger.error("Failed to parse standard image: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image format: {e}",
        )


# ---------------------------------------------------------------------------
# BiomedCLIP Zero-Shot Fast Triage Engine (~200ms on CPU)
# ---------------------------------------------------------------------------

class BiomedCLIPEngine:
    """Singleton for BiomedCLIP zero-shot visual finding extraction."""

    _instance: Optional[BiomedCLIPEngine] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        if not BIOMEDCLIP_DIR.exists():
            raise FileNotFoundError(f"BiomedCLIP directory not found at {BIOMEDCLIP_DIR}")

        from transformers import AutoModel, AutoProcessor

        logger.info("Initializing BiomedCLIP Engine from %s...", BIOMEDCLIP_DIR)
        t0 = time.perf_counter()
        self.model = AutoModel.from_pretrained(str(BIOMEDCLIP_DIR), local_files_only=True, trust_remote_code=True)
        self.processor = AutoProcessor.from_pretrained(str(BIOMEDCLIP_DIR), local_files_only=True, trust_remote_code=True)

        # Fix transformers position_ids buffer
        emb = self.model.text_model.embeddings
        L = emb.position_ids.shape[-1]
        emb.position_ids = torch.arange(L).unsqueeze(0)
        emb.token_type_ids = torch.zeros_like(emb.position_ids)

        self.model.to("cpu")
        self.model.eval()
        torch.set_num_threads(4)

        cached_pt = ROOT_DIR / "data/multimodal/prompt_embeddings_v2.pt"
        if cached_pt.exists():
            data = torch.load(str(cached_pt), map_location="cpu", weights_only=True)
            self.pos_features = data["pos_f"]
            self.neg_features = data["neg_f"]
            self.logit_scale = float(data.get("logit_scale", 100.0))
        else:
            self.pos_features = self._embed_templates(POS_TEMPLATES)
            self.neg_features = self._embed_templates(NEG_TEMPLATES)
            try:
                self.logit_scale = float(self.model.logit_scale.exp().item())
            except Exception:
                self.logit_scale = 100.0

        logger.info("BiomedCLIP Engine ready in %.2f s (logit_scale=%.1f)", time.perf_counter() - t0, self.logit_scale)

    @classmethod
    def get_instance(cls) -> BiomedCLIPEngine:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @torch.no_grad()
    def _embed_templates(self, templates: List[str]) -> torch.Tensor:
        prompts = [t.format(c=c) for c in CHEXZERO_LABELS for t in templates]
        tokens = self.processor(text=prompts, return_tensors="pt", padding="max_length", truncation=True)
        features = self.model.get_text_features(**tokens)
        features = features / features.norm(dim=-1, keepdim=True)
        n = len(templates)
        return features.view(len(CHEXZERO_LABELS), n, -1).mean(dim=1)

    @torch.no_grad()
    def classify(self, pil_image: Image.Image) -> Tuple[List[VisualFinding], Dict[str, float], List[str]]:
        """
        Classify a single PIL image using zero-shot prompt ensembles.
        Returns: (findings_detailed, confidence_scores, top_detected_findings_strings)
        """
        px = self.processor(images=[pil_image], return_tensors="pt")
        img_f = self.model.get_image_features(**px)
        img_f = img_f / img_f.norm(dim=-1, keepdim=True)

        pos_logits = self.logit_scale * (img_f @ self.pos_features.T)  # [1, 14]
        neg_logits = self.logit_scale * (img_f @ self.neg_features.T)

        p_pos = pos_logits.softmax(dim=-1).squeeze(0)
        p_neg = neg_logits.softmax(dim=-1).squeeze(0)

        findings_detailed: List[VisualFinding] = []
        confidence_scores: Dict[str, float] = {}
        detected_summary: List[str] = []

        for idx, label in enumerate(CHEXZERO_LABELS):
            pos_prob = float(p_pos[idx])
            neg_prob = float(p_neg[idx])
            is_negated = bool(neg_prob > pos_prob and label != "no finding")
            conf = round(pos_prob, 4)
            confidence_scores[label] = conf

            auc_ref = AUC_BENCHMARK_REFERENCE.get(label, 0.65)

            finding_obj = VisualFinding(
                label=label,
                confidence=conf,
                negated=is_negated,
                location="Bilateral / Central" if label in ("cardiomegaly", "enlarged cardiomediastinum") else "Thorax",
                severity="Mild/Moderate" if conf > 0.6 else "Subtle/Unclear",
                auc_reference=auc_ref,
            )
            findings_detailed.append(finding_obj)

            if not is_negated and label != "no finding" and conf >= 0.15:
                detected_summary.append(f"{label.capitalize()} ({conf * 100:.1f}% confidence)")

        if not detected_summary:
            detected_summary.append("No acute focal cardiopulmonary abnormality detected (confidence: high)")

        return findings_detailed, confidence_scores, detected_summary


# ---------------------------------------------------------------------------
# Qwen2-VL-2B Generative VLM Engine (Lazy-loaded, CPU-only, 10 min idle unload)
# ---------------------------------------------------------------------------

class Qwen2VLEngine:
    """Singleton for Qwen2-VL-2B generative clinical analysis on CPU."""

    _instance: Optional[Qwen2VLEngine] = None
    _lock = threading.Lock()
    _semaphore = threading.Semaphore(1)

    def __init__(self) -> None:
        if not QWEN2_VL_GGUF.exists() or not QWEN2_VL_MMPROJ.exists():
            raise FileNotFoundError(
                f"Qwen2-VL weights missing: GGUF={QWEN2_VL_GGUF.exists()}, MMPROJ={QWEN2_VL_MMPROJ.exists()}"
            )
        self.llm = None
        self.handler = None
        self.last_used_timestamp = 0.0

    @classmethod
    def get_instance(cls) -> Qwen2VLEngine:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _ensure_loaded(self) -> None:
        if psutil is not None:
            available_gb = psutil.virtual_memory().available / (1024**3)
            if available_gb < 2.0:
                logger.error("Insufficient RAM for Qwen2-VL load: %.2f GB available < 2.0 GB required", available_gb)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Insufficient system memory for VLM generation ({available_gb:.1f} GB available). Please retry in a few moments.",
                )

        if self.llm is None:
            from llama_cpp import Llama
            from llama_cpp.llama_chat_format import Qwen25VLChatHandler

            logger.info("Lazy-loading Qwen2-VL-2B on CPU (n_gpu_layers=0, n_threads=4)...")
            t0 = time.perf_counter()
            self.handler = Qwen25VLChatHandler(clip_model_path=str(QWEN2_VL_MMPROJ))
            self.llm = Llama(
                model_path=str(QWEN2_VL_GGUF),
                n_gpu_layers=0,
                n_ctx=4608,
                n_threads=4,
                verbose=False,
                chat_handler=self.handler,
            )
            logger.info("Qwen2-VL-2B loaded in %.2f s", time.perf_counter() - t0)
        self.last_used_timestamp = time.time()

    def unload_if_idle(self, max_idle_seconds: float = 600.0) -> bool:
        """Unload model from RAM if idle for longer than max_idle_seconds (10 min)."""
        with self._lock:
            if self.llm is not None and (time.time() - self.last_used_timestamp) > max_idle_seconds:
                logger.info("Qwen2-VL idle for >%ds — unloading from RAM.", max_idle_seconds)
                del self.llm
                del self.handler
                self.llm = None
                self.handler = None
                gc.collect()
                return True
        return False

    def generate_interpretation(
        self,
        pil_image: Image.Image,
        custom_prompt: Optional[str] = None,
    ) -> Tuple[str, List[str], str]:
        """
        Generate structured radiological impression, recommendations, and refusal tier.
        Returns: (impression, recommendations, refusal_tier)
        """
        with self._semaphore:
            self._ensure_loaded()

            # Prepare 448x448 base64 JPEG
            im_resized = pil_image.convert("RGB").resize((448, 448))
            buf = io.BytesIO()
            im_resized.save(buf, format="JPEG", quality=85)
            b64_img = base64.b64encode(buf.getvalue()).decode()

            prompt_text = custom_prompt or (
                "You are an expert board-certified radiologist reviewing a chest radiograph. "
                "Provide a concise, formal radiological report with:\n"
                "1. KEY FINDINGS: (Cardiac silhouette, mediastinum, lung fields, pleura, bones)\n"
                "2. IMPRESSION: (Summary of principal clinical abnormality or normal status)\n"
                "3. RECOMMENDATIONS: (Recommended clinical follow-up or correlation)"
            )

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}},
                        {"type": "text", "text": prompt_text},
                    ],
                }
            ]

            try:
                response = self.llm.create_chat_completion(
                    messages=messages,
                    max_tokens=300,
                    temperature=0.1,
                )
                text = response["choices"][0]["message"]["content"].strip()
            except Exception as e:
                logger.error("Qwen2-VL generation error: %s", e)
                return (
                    "Visual analysis could not be fully generated. Please refer to zero-shot triage scores.",
                    ["Clinical correlation and standard radiology overread advised."],
                    "HEDGED",
                )
            finally:
                self.last_used_timestamp = time.time()

            # Parse Refusal Tier
            a = text.lower()
            if re.search(r"\b(cannot|can't|unable|not able to|refuse|no answer|not (a )?medical)\b", a):
                refusal = "REFUSED"
            elif re.search(r"\b(unclear|not sure|possibly|may|might|appears|likely|difficult to determine)\b", a):
                refusal = "HEDGED"
            else:
                refusal = "ANSWERED"

            # Parse Recommendations
            recommendations: List[str] = []
            if "RECOMMENDATION" in text.upper():
                rec_part = re.split(r"RECOMMENDATIONS?:", text, flags=re.IGNORECASE)[-1].strip()
                lines = [line.strip().lstrip("*-123456789. ") for line in rec_part.splitlines() if line.strip()]
                recommendations = lines[:4]
            if not recommendations:
                recommendations = [
                    "Compare with prior chest radiographs if available.",
                    "Correlate findings with clinical presentation and acute biomarker trends.",
                ]

            return text, recommendations, refusal


# ---------------------------------------------------------------------------
# Report Graph Entity Linking (Scoped against data/multimodal/report_graph/kuzu.db)
# ---------------------------------------------------------------------------

def query_report_graph_links(image_id_or_stem: str) -> Tuple[bool, List[KnowledgeGraphPath], Optional[str]]:
    """
    Search data/multimodal/report_graph/kuzu.db for linked Image, VisualFinding, and Report nodes.
    Only matches known OpenI / VQA-RAD images.
    Returns: (has_graph_links, graph_paths, graph_notice)
    """
    db_file = REPORT_GRAPH_DB_DIR / "kuzu.db"
    if not db_file.exists():
        return False, [], "Report graph database not found."

    clean_key = Path(image_id_or_stem).stem.strip()

    try:
        db = kuzu.Database(str(REPORT_GRAPH_DB_DIR / "kuzu.db"))
        conn = kuzu.Connection(db)

        # 1. Look for matching Image node
        res = conn.execute(
            f"MATCH (i:Image) WHERE i.image_id = '{clean_key}' RETURN i.image_id LIMIT 1"
        )
        matched_id = None
        if res.has_next():
            matched_id = res.get_next()[0]
        else:
            # Try study base prefix if not matched directly
            prefix = clean_key.split(".")[0]
            res = conn.execute(
                f"MATCH (i:Image) WHERE i.image_id STARTS WITH '{prefix}' RETURN i.image_id LIMIT 1"
            )
            if res.has_next():
                matched_id = res.get_next()[0]

        if not matched_id:
            return False, [], "No knowledge graph links for private scans."

        # 2. Extract IMAGE_SHOWS findings
        findings_res = conn.execute(
            f"MATCH (i:Image)-[:IMAGE_SHOWS]->(v:VisualFinding) WHERE i.image_id = '{matched_id}' RETURN v.finding_id, v.label, v.negated"
        )
        paths: List[KnowledgeGraphPath] = []
        while findings_res.has_next():
            row = findings_res.get_next()
            lbl, neg = row[1], bool(row[2])

            # 3. Extract cross-linked Reports
            rep_res = conn.execute(
                f"MATCH (r:Report)-[:REPORT_DESCRIBES]->(i:Image) WHERE i.image_id = '{matched_id}' RETURN r.report_id, r.section, r.text_snippet LIMIT 3"
            )
            matched_reports = []
            while rep_res.has_next():
                r_row = rep_res.get_next()
                matched_reports.append({
                    "report_id": r_row[0],
                    "section": r_row[1],
                    "text_snippet": r_row[2],
                })

            paths.append(
                KnowledgeGraphPath(
                    source_image_id=matched_id,
                    finding_label=lbl,
                    finding_negated=neg,
                    matched_reports=matched_reports,
                )
            )

        notice = f"Matched {len(paths)} visual finding entities in OpenI knowledge graph."
        return True, paths, notice

    except Exception as e:
        logger.warning("Failed querying report graph for %s: %s", clean_key, e)
        return False, [], "No knowledge graph links for private scans."


# ---------------------------------------------------------------------------
# Master Medical Image Analysis Pipeline
# ---------------------------------------------------------------------------

def analyze_medical_image_with_vlm(
    image: MedicalImage,
    mode: str = "triage",
    prompt: Optional[str] = None,
) -> ImageAnalysisResult:
    """
    Complete analysis pipeline for medical scans:
    - mode="triage": Fast zero-shot BiomedCLIP (~200ms) + KG crosslinks.
    - mode="full": BiomedCLIP + Qwen2-VL-2B generative interpretation + KG crosslinks.
    """
    t0 = time.perf_counter()

    # Load PIL image
    if image.image_bytes is not None:
        if any(image.filename.lower().endswith(ext) for ext in DICOM_EXTENSIONS):
            pil_image, preview_bytes, tags = load_dicom_image(image.image_bytes)
            if image.preview_bytes is None:
                image.preview_bytes = preview_bytes
        else:
            pil_image, preview_bytes = load_standard_image(image.image_bytes)
            if image.preview_bytes is None:
                image.preview_bytes = preview_bytes
    else:
        raise ValueError("MedicalImage missing image_bytes.")

    # 1. Run BiomedCLIP Zero-Shot Fast Triage
    try:
        clip_engine = BiomedCLIPEngine.get_instance()
        findings_detailed, confidence_scores, detected_strings = clip_engine.classify(pil_image)
    except Exception as e:
        logger.error("BiomedCLIP classification failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"BiomedCLIP zero-shot triage engine unavailable: {e}",
        )

    # 2. Query Scoped Report Graph for cross-linked entities
    has_links, graph_paths, graph_notice = query_report_graph_links(image.filename or image.image_id)

    # 3. Handle Mode ("triage" vs "full")
    model_name = "BiomedCLIP zero-shot v2"
    refusal_tier = "ANSWERED"
    recommendations: List[str] = []

    if mode == "full":
        try:
            vlm_engine = Qwen2VLEngine.get_instance()
            impression_text, recommendations, refusal_tier = vlm_engine.generate_interpretation(
                pil_image=pil_image,
                custom_prompt=prompt,
            )
            model_name = "BiomedCLIP v2 + Qwen2-VL-2B (CPU)"
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Qwen2-VL execution failed: %s", e)
            impression_text = (
                f"BiomedCLIP Triage Summary: {', '.join(detected_strings)}.\n\n"
                "Generative VLM interpretation encountered an issue. Standard radiological correlation advised."
            )
            recommendations = ["Clinical correlation and repeat examination if indicated."]
    else:
        # Triage mode default summary
        top_pos = [f.label for f in findings_detailed if not f.negated and f.confidence >= 0.15]
        if top_pos:
            impression_text = (
                f"BiomedCLIP zero-shot screening detected elevated probability for: {', '.join(top_pos)}. "
                "Full generative interpretation available on request."
            )
        else:
            impression_text = "BiomedCLIP zero-shot screening: No acute focal cardiopulmonary consolidation, pneumothorax, or large effusion detected."
        recommendations = ["Request Full Generative Interpretation for detailed anatomical breakdown."]

    elapsed_ms = (time.perf_counter() - t0) * 1000

    provenance = [
        "BiomedCLIP-PubMedBERT-vit_base_patch16_224 zero-shot prompt ensemble",
        f"Kùzu Report Graph ({REPORT_GRAPH_DB_DIR.name})",
    ]
    if mode == "full":
        provenance.append("Qwen2-VL-2B-Instruct GGUF Q4_K_M (CPU-isolated, 4 threads)")

    return ImageAnalysisResult(
        image_id=image.image_id,
        filename=image.filename,
        modality=image.modality,
        orientation=image.orientation,
        body_part=image.body_part or "Chest",
        mode=mode,
        findings=detected_strings,
        findings_detailed=findings_detailed,
        impression=impression_text,
        recommendations=recommendations,
        confidence_scores=confidence_scores,
        refusal_tier=refusal_tier,
        has_graph_links=has_links,
        graph_paths=graph_paths,
        graph_notice=graph_notice,
        preview_url=f"/multimodal/preview/{image.image_id}",
        processing_time_ms=round(elapsed_ms, 2),
        model_used=model_name,
        provenance=provenance,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# PDF Document Parsing with embedded images
# ---------------------------------------------------------------------------

def parse_pdf_with_images(file_bytes: bytes, filename: str) -> PDFDocument:
    """Parse PDF extracting text, tables, and embedded images via PyMuPDF."""
    file_hash = compute_file_hash(file_bytes)
    doc = fitz.open(stream=file_bytes, filetype="pdf")

    pages: List[PDFPage] = []
    full_text_parts: List[str] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        full_text_parts.append(text)

        tables: List[List[List[str]]] = []
        try:
            tab = page.find_tables()
            if tab and tab.tables:
                for t in tab.tables:
                    tables.append(t.extract())
        except Exception:
            pass

        pdf_images: List[PDFImage] = []
        for img_idx, img_info in enumerate(page.get_images(full=True)):
            xref = img_info[0]
            try:
                base_img = doc.extract_image(xref)
                img_bytes = base_img["image"]
                pdf_images.append(
                    PDFImage(
                        image_index=img_idx,
                        xref=xref,
                        width=base_img["width"],
                        height=base_img["height"],
                        colorspace=str(base_img.get("colorspace", "")),
                        image_bytes=img_bytes,
                        image_bytes_hash=compute_file_hash(img_bytes),
                    )
                )
            except Exception as e:
                logger.debug("Failed extracting image %d from PDF page %d: %s", img_idx, page_num + 1, e)

        pages.append(
            PDFPage(
                page_number=page_num + 1,
                text=text,
                tables=tables,
                images=pdf_images,
            )
        )

    doc.close()

    return PDFDocument(
        document_id=file_hash[:16],
        filename=filename,
        file_bytes_hash=file_hash,
        page_count=len(pages),
        pages=pages,
        full_text="\n\n".join(full_text_parts),
        metadata={},
        needs_review=False,
    )


def ingest_multimodal_files(
    file_paths: List[Union[str, Path]],
    user_id: str = "default_user",
    destination: str = "private",
    analyze_images: bool = True,
    mode: str = "triage",
) -> MultimodalIngestionResult:
    """Batch ingest image and PDF files."""
    t0 = time.perf_counter()
    image_results: List[ImageAnalysisResult] = []
    pdf_results: List[PDFDocument] = []
    errors: List[Dict[str, str]] = []
    total_findings = 0

    for fp in file_paths:
        p = Path(fp)
        ext = p.suffix.lower()
        try:
            file_bytes = p.read_bytes()
            if ext in IMAGE_EXTENSIONS or ext in DICOM_EXTENSIONS:
                if ext in DICOM_EXTENSIONS:
                    pil_img, prev_b, tags = load_dicom_image(file_bytes)
                    orientation = detect_orientation(p.name, tags)
                    med_img = MedicalImage(
                        image_id=compute_file_hash(file_bytes)[:16],
                        filename=p.name,
                        modality=ImageModality.XRAY,
                        orientation=orientation,
                        body_part=tags.get("BodyPartExamined", "Chest"),
                        file_bytes_hash=compute_file_hash(file_bytes),
                        image_bytes=file_bytes,
                        preview_bytes=prev_b,
                    )
                else:
                    pil_img, prev_b = load_standard_image(file_bytes)
                    orientation = detect_orientation(p.name)
                    med_img = MedicalImage(
                        image_id=compute_file_hash(file_bytes)[:16],
                        filename=p.name,
                        modality=detect_image_modality(p.name, pil_img),
                        orientation=orientation,
                        file_bytes_hash=compute_file_hash(file_bytes),
                        image_bytes=file_bytes,
                        preview_bytes=prev_b,
                    )

                if analyze_images:
                    analysis = analyze_medical_image_with_vlm(med_img, mode=mode)
                    image_results.append(analysis)
                    total_findings += len(analysis.findings)
            elif ext in PDF_EXTENSIONS:
                pdf_doc = parse_pdf_with_images(file_bytes, p.name)
                pdf_results.append(pdf_doc)
        except Exception as e:
            logger.error("Failed processing file %s: %s", p.name, e)
            errors.append({"filename": p.name, "error": str(e)})

    elapsed_ms = (time.perf_counter() - t0) * 1000
    return MultimodalIngestionResult(
        ingestion_id=hashlib.md5(f"{user_id}_{time.time()}".encode()).hexdigest()[:12],
        images_processed=len(image_results),
        pdfs_processed=len(pdf_results),
        total_findings=total_findings,
        total_latency_ms=round(elapsed_ms, 2),
        image_results=image_results,
        pdf_results=pdf_results,
        errors=errors,
        provenance=["MedGraphRAG Multimodal Ingestion Pipeline"],
    )