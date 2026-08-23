"""
MedGraphRAG Backend — Multimodal Parser
========================================
Parses medical images (X-ray, CT, MRI, pathology) and PDF documents using
vision-language models (VLMs) and OCR for clinical content extraction.

Supports:
- DICOM (.dcm) medical images via pydicom + PIL
- Standard images (PNG, JPG, TIFF) via PIL
- PDF documents with embedded images via PyMuPDF + VLM
- OCR fallback for text extraction from images
"""

from __future__ import annotations

import hashlib
import io
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import fitz  # PyMuPDF
from PIL import Image
import numpy as np

from app.config import settings
from app.core.report.schemas import ParsedReport
from app.multimodal.schemas import (
    ImageAnalysisResult,
    ImageModality,
    ImageOrientation,
    MedicalImage,
    MultimodalIngestionResult,
    PDFDocument,
    PDFImage,
    PDFPage,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Image format detection
# ---------------------------------------------------------------------------

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}
DICOM_EXTENSIONS = {".dcm", ".dicom"}
PDF_EXTENSIONS = {".pdf"}


def detect_image_modality(filename: str, image: Optional[Image.Image] = None) -> ImageModality:
    """Detect medical imaging modality from filename and/or image characteristics."""
    filename_lower = filename.lower()

    # Check filename for modality hints
    if any(kw in filename_lower for kw in ["xray", "x-ray", "chest", "radiograph", "cxr"]):
        return ImageModality.XRAY
    if any(kw in filename_lower for kw in ["ct", "cat_scan", "computed_tomography"]):
        return ImageModality.CT
    if any(kw in filename_lower for kw in ["mri", "magnetic_resonance", "t1", "t2", "flair", "dwi"]):
        return ImageModality.MRI
    if any(kw in filename_lower for kw in ["us", "ultrasound", "sonogram", "echo"]):
        return ImageModality.ULTRASOUND
    if any(kw in filename_lower for kw in ["path", "histology", "h&e", "hne", "biopsy", "slide"]):
        return ImageModality.PATHOLOGY
    if any(kw in filename_lower for kw in ["derm", "skin", "lesion", "melanoma"]):
        return ImageModality.DERMATOLOGY
    if any(kw in filename_lower for kw in ["oct", "optical_coherence"]):
        return ImageModality.OCT
    if any(kw in filename_lower for kw in ["fundus", "retina", "ophthalm"]):
        return ImageModality.FUNDUS
    if any(kw in filename_lower for kw in ["endo", "gastroscopy", "colonoscopy", "bronchoscopy"]):
        return ImageModality.ENDOSCOPY

    # Could add image-based detection here (e.g., using a small classifier)
    return ImageModality.UNKNOWN


def detect_orientation(filename: str, dicom_tags: Optional[Dict[str, Any]] = None) -> ImageOrientation:
    """Detect image orientation/view from filename or DICOM tags."""
    filename_lower = filename.lower()

    if dicom_tags:
        view = dicom_tags.get("ViewPosition", "").upper()
        if view in ("AP", "PA", "LATERAL", "LPO", "RPO", "LAO", "RAO"):
            if view in ("LPO", "RPO", "LAO", "RAO"):
                return ImageOrientation.OBLIQUE
            return ImageOrientation(view)

    # Filename-based heuristics
    if "ap" in filename_lower or "anteroposterior" in filename_lower:
        return ImageOrientation.AP
    if "pa" in filename_lower or "posteroanterior" in filename_lower:
        return ImageOrientation.PA
    if "lat" in filename_lower or "lateral" in filename_lower:
        return ImageOrientation.LATERAL
    if "obl" in filename_lower or "oblique" in filename_lower:
        return ImageOrientation.OBLIQUE
    if "axial" in filename_lower or "transverse" in filename_lower:
        return ImageOrientation.AXIAL
    if "coronal" in filename_lower:
        return ImageOrientation.CORONAL
    if "sagittal" in filename_lower or "sag" in filename_lower:
        return ImageOrientation.SAGITTAL

    return ImageOrientation.UNKNOWN


def compute_file_hash(file_bytes: bytes) -> str:
    """Compute SHA-256 hash of file bytes."""
    return hashlib.sha256(file_bytes).hexdigest()


# ---------------------------------------------------------------------------
# DICOM Image Loading
# ---------------------------------------------------------------------------

def load_dicom_image(file_bytes: bytes) -> tuple[Image.Image, Dict[str, Any]]:
    """
    Load DICOM image and extract metadata.
    Returns (PIL Image, dict of DICOM tags).
    """
    try:
        import pydicom
        from pydicom.pixel_data_handlers.util import apply_voi_lut
    except ImportError:
        raise ImportError("pydicom is required for DICOM support. Install with: pip install pydicom")

    dicom_bytes = io.BytesIO(file_bytes)
    ds = pydicom.dcmread(dicom_bytes)

    # Extract pixel array
    pixel_array = ds.pixel_array

    # Apply VOI LUT if available (window/level)
    try:
        pixel_array = apply_voi_lut(pixel_array, ds)
    except Exception:
        pass  # Continue without VOI LUT

    # Normalize to 0-255 for PIL
    if pixel_array.dtype != np.uint8:
        pmin, pmax = pixel_array.min(), pixel_array.max()
        if pmax > pmin:
            pixel_array = ((pixel_array - pmin) / (pmax - pmin) * 255).astype(np.uint8)
        else:
            pixel_array = np.zeros_like(pixel_array, dtype=np.uint8)

    # Handle multi-frame (take first frame for now)
    if pixel_array.ndim == 3 and pixel_array.shape[0] > 1:
        logger.info("Multi-frame DICOM detected (%d frames), using first frame", pixel_array.shape[0])
        pixel_array = pixel_array[0]

    # Convert to PIL Image
    if pixel_array.ndim == 2:
        pil_image = Image.fromarray(pixel_array, mode="L")
    elif pixel_array.ndim == 3 and pixel_array.shape[2] == 3:
        pil_image = Image.fromarray(pixel_array, mode="RGB")
    else:
        # Single channel but 3D
        pil_image = Image.fromarray(pixel_array.squeeze(), mode="L")

    # Extract relevant DICOM tags
    dicom_tags = {
        "PatientID": str(ds.get("PatientID", "")),
        "StudyID": str(ds.get("StudyID", "")),
        "SeriesNumber": str(ds.get("SeriesNumber", "")),
        "InstanceNumber": str(ds.get("InstanceNumber", "")),
        "Modality": str(ds.get("Modality", "")),
        "BodyPartExamined": str(ds.get("BodyPartExamined", "")),
        "ViewPosition": str(ds.get("ViewPosition", "")),
        "PatientSex": str(ds.get("PatientSex", "")),
        "PatientAge": str(ds.get("PatientAge", "")),
        "StudyDate": str(ds.get("StudyDate", "")),
        "SeriesDate": str(ds.get("SeriesDate", "")),
        "PixelSpacing": [float(x) for x in ds.get("PixelSpacing", [])] if "PixelSpacing" in ds else None,
        "ImageOrientationPatient": [float(x) for x in ds.get("ImageOrientationPatient", [])] if "ImageOrientationPatient" in ds else None,
        "Rows": int(ds.get("Rows", 0)),
        "Columns": int(ds.get("Columns", 0)),
    }

    return pil_image, dicom_tags


# ---------------------------------------------------------------------------
# Standard Image Loading
# ---------------------------------------------------------------------------

def load_standard_image(file_bytes: bytes) -> Image.Image:
    """Load standard image formats (PNG, JPG, TIFF, etc.) via PIL."""
    image_stream = io.BytesIO(file_bytes)
    img = Image.open(image_stream)
    # Force load to catch corruption early
    img.load()
    return img.convert("RGB") if img.mode != "RGB" else img


# ---------------------------------------------------------------------------
# PDF Parsing with Embedded Images
# ---------------------------------------------------------------------------

def parse_pdf_with_images(file_bytes: bytes, filename: str) -> PDFDocument:
    """
    Parse PDF document, extracting text, tables, and embedded images.
    Embedded images are returned as PDFImage objects for downstream VLM processing.
    """
    file_hash = compute_file_hash(file_bytes)
    doc = fitz.open(stream=file_bytes, filetype="pdf")

    pages: List[PDFPage] = []
    full_text_parts: List[str] = []

    for page_num in range(len(doc)):
        page = doc[page_num]

        # Extract text
        text = page.get_text("text")
        full_text_parts.append(text)

        # Extract tables
        tables = []
        try:
            # Use pdfplumber for better table extraction
            import pdfplumber
            pdf_bytes_io = io.BytesIO(file_bytes)
            with pdfplumber.open(pdf_bytes_io) as pdf:
                if page_num < len(pdf.pages):
                    pl_page = pdf.pages[page_num]
                    extracted_tables = pl_page.extract_tables()
                    if extracted_tables:
                        for table in extracted_tables:
                            if table:
                                tables.append([[str(cell) if cell else "" for cell in row] for row in table])
        except Exception as e:
            logger.debug("Table extraction failed for page %d: %s", page_num + 1, e)

        # Extract embedded images
        pdf_images: List[PDFImage] = []
        image_list = page.get_images(full=True)

        for img_idx, img_info in enumerate(image_list):
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                img_bytes = base_image["image"]
                img_ext = base_image["ext"]
                img_width = base_image["width"]
                img_height = base_image["height"]
                colorspace = base_image.get("colorspace", "")

                img_hash = compute_file_hash(img_bytes)

                pdf_image = PDFImage(
                    image_index=img_idx,
                    xref=xref,
                    width=img_width,
                    height=img_height,
                    colorspace=str(colorspace),
                    image_bytes=img_bytes,
                    image_bytes_hash=img_hash,
                )
                pdf_images.append(pdf_image)
            except Exception as e:
                logger.warning("Failed to extract image %d from page %d: %s", img_idx, page_num + 1, e)

        pdf_page = PDFPage(
            page_number=page_num + 1,
            text=text,
            tables=tables,
            images=pdf_images,
        )
        pages.append(pdf_page)

    doc.close()

    # Extract PDF metadata
    pdf_metadata = {}
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pdf_metadata = doc.metadata or {}
        doc.close()
    except Exception:
        pass

    return PDFDocument(
        document_id=file_hash[:16],
        filename=filename,
        file_bytes_hash=file_hash,
        page_count=len(pages),
        pages=pages,
        full_text="\n\n".join(full_text_parts),
        metadata=pdf_metadata,
    )


# ---------------------------------------------------------------------------
# VLM Analysis (placeholder for integration with actual VLM)
# ---------------------------------------------------------------------------

def analyze_medical_image_with_vlm(
    image: MedicalImage,
    prompt: Optional[str] = None,
) -> ImageAnalysisResult:
    """
    Analyze a medical image using a Vision-Language Model.

    This is a placeholder that integrates with the actual VLM backend.
    In production, this would call a VLM (e.g., LLaVA-Med, Med-Flamingo,
    GPT-4V, or a fine-tuned medical VLM).
    """
    start_time = time.perf_counter()

    # Default medical imaging prompt
    if prompt is None:
        prompt = (
            "You are a board-certified radiologist. Analyze this medical image and provide: "
            "1. Key findings (list each finding separately) "
            "2. Overall impression "
            "3. Recommendations for follow-up "
            "Format as structured JSON."
        )

    # TODO: Integrate with actual VLM
    # For now, return a structured placeholder result
    # The actual VLM call would go here

    logger.info("VLM analysis requested for image %s (modality: %s)", image.image_id, image.modality)
    from app.multimodal.device import resolve_vlm_device
    _device = resolve_vlm_device()
    logger.warning(
        "VLM backend not yet integrated (device=%s) - returning placeholder",
        _device,
    )

    # Placeholder result structure
    result = ImageAnalysisResult(
        image_id=image.image_id,
        findings=["VLM analysis placeholder - integrate actual model"],
        findings_detailed=[{
            "finding": "Placeholder finding",
            "location": "Unknown",
            "severity": "Unknown",
            "confidence": 0.0,
        }],
        impression="VLM analysis not yet implemented. Connect to vision-language model.",
        recommendations=["Integrate VLM backend for medical image analysis"],
        confidence_scores={"placeholder": 0.0},
        modality=image.modality,
        processing_time_ms=(time.perf_counter() - start_time) * 1000,
        model_used="placeholder",
        provenance=["VLM analysis pipeline - requires integration"],
    )

    return result


# ---------------------------------------------------------------------------
# OCR Text Extraction from Images
# ---------------------------------------------------------------------------

def extract_text_from_image_ocr(image: Image.Image) -> tuple[str, float]:
    """
    Extract text from image using OCR.
    Returns (extracted_text, confidence_score).
    """
    try:
        import easyocr
        reader = easyocr.Reader(['en'], gpu=False)
        results = reader.readtext(np.array(image))
        text_parts = [r[1] for r in results]
        confidences = [r[2] for r in results]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        return "\n".join(text_parts), avg_confidence
    except ImportError:
        logger.warning("EasyOCR not installed, trying pytesseract")

    try:
        import pytesseract
        text = pytesseract.image_to_string(image)
        # pytesseract doesn't give easy confidence, use heuristic
        confidence = 0.7 if len(text.strip()) > 10 else 0.3
        return text, confidence
    except ImportError:
        logger.warning("No OCR backend available (easyocr or pytesseract)")
        return "", 0.0


# ---------------------------------------------------------------------------
# Main Ingestion Pipeline
# ---------------------------------------------------------------------------

def ingest_multimodal_files(
    file_paths: List[Union[str, Path]],
    user_id: str = "default_user",
    destination: str = "private",
    analyze_images: bool = True,
) -> MultimodalIngestionResult:
    """
    Main multimodal ingestion pipeline.

    Processes a list of files (images, PDFs) and extracts structured clinical content
    for integration with the MedGraphRAG retrieval and generation pipeline.

    Parameters
    ----------
    file_paths : List of paths to image/PDF files
    user_id : User identifier for private storage
    destination : Storage destination ('global' or 'private')
    analyze_images : Whether to run VLM analysis on images

    Returns
    -------
    MultimodalIngestionResult with all extracted content and analyses
    """
    start_time = time.perf_counter()
    ingestion_id = f"ingest_{user_id}_{int(time.time())}"

    image_results: List[ImageAnalysisResult] = []
    pdf_results: List[PDFDocument] = []
    errors: List[Dict[str, str]] = []
    provenance: List[str] = []

    for file_path in file_paths:
        path = Path(file_path)
        if not path.exists():
            errors.append({"file": str(path), "error": "File not found"})
            continue

        try:
            file_bytes = path.read_bytes()
            file_hash = compute_file_hash(file_bytes)
            ext = path.suffix.lower()

            # Process images
            if ext in IMAGE_EXTENSIONS:
                logger.info("Processing image: %s", path.name)
                pil_image = load_standard_image(file_bytes)

                modality = detect_image_modality(path.name, pil_image)
                orientation = detect_orientation(path.name)

                medical_image = MedicalImage(
                    image_id=file_hash[:16],
                    filename=path.name,
                    modality=modality,
                    orientation=orientation,
                    file_bytes_hash=file_hash,
                    image_bytes=file_bytes,
                    image_shape=[pil_image.height, pil_image.width, 3 if pil_image.mode == "RGB" else 1],
                )

                if analyze_images:
                    analysis = analyze_medical_image_with_vlm(medical_image)
                    image_results.append(analysis)
                    provenance.append(f"VLM analysis: {path.name}")
                else:
                    provenance.append(f"Image ingested (no VLM): {path.name}")

            # Process DICOM
            elif ext in DICOM_EXTENSIONS:
                logger.info("Processing DICOM: %s", path.name)
                pil_image, dicom_tags = load_dicom_image(file_bytes)

                modality = detect_image_modality(path.name, pil_image)
                orientation = detect_orientation(path.name, dicom_tags)

                medical_image = MedicalImage(
                    image_id=file_hash[:16],
                    filename=path.name,
                    modality=modality,
                    orientation=orientation,
                    body_part=dicom_tags.get("BodyPartExamined"),
                    patient_id=dicom_tags.get("PatientID"),
                    study_id=dicom_tags.get("StudyID"),
                    series_id=dicom_tags.get("SeriesNumber"),
                    instance_id=dicom_tags.get("InstanceNumber"),
                    acquisition_date=dicom_tags.get("StudyDate"),
                    pixel_spacing=dicom_tags.get("PixelSpacing"),
                    image_shape=[pil_image.height, pil_image.width, 1],
                    file_bytes_hash=file_hash,
                    image_bytes=file_bytes,
                )

                if analyze_images:
                    analysis = analyze_medical_image_with_vlm(medical_image)
                    image_results.append(analysis)
                    provenance.append(f"VLM analysis (DICOM): {path.name}")
                else:
                    provenance.append(f"DICOM ingested (no VLM): {path.name}")

            # Process PDF
            elif ext in PDF_EXTENSIONS:
                logger.info("Processing PDF: %s", path.name)
                pdf_doc = parse_pdf_with_images(file_bytes, path.name)
                pdf_results.append(pdf_doc)

                # Also create ParsedReport for compatibility with existing report pipeline
                provenance.append(f"PDF parsed: {path.name} ({pdf_doc.page_count} pages)")

                # Optionally analyze embedded images in PDF
                if analyze_images:
                    for page in pdf_doc.pages:
                        for pdf_img in page.images:
                            if pdf_img.image_bytes:
                                try:
                                    pil_img = Image.open(io.BytesIO(pdf_img.image_bytes))
                                    pdf_img_hash = compute_file_hash(pdf_img.image_bytes)

                                    med_img = MedicalImage(
                                        image_id=f"{pdf_doc.document_id}_p{page.page_number}_img{pdf_img.image_index}",
                                        filename=f"{path.name}_p{page.page_number}_img{pdf_img.image_index}",
                                        modality=ImageModality.UNKNOWN,
                                        file_bytes_hash=pdf_img_hash,
                                        image_bytes=pdf_img.image_bytes,
                                        image_shape=[pil_img.height, pil_img.width, 3],
                                    )
                                    analysis = analyze_medical_image_with_vlm(med_img)
                                    image_results.append(analysis)
                                    pdf_img.analysis = analysis
                                    provenance.append(f"VLM analysis (PDF embedded): {path.name} page {page.page_number}")
                                except Exception as e:
                                    logger.warning("Failed to analyze embedded image in PDF %s: %s", path.name, e)

            else:
                errors.append({"file": str(path), "error": f"Unsupported file type: {ext}"})

        except Exception as e:
            logger.error("Failed to process %s: %s", path, e)
            errors.append({"file": str(path), "error": str(e)})

    total_latency = (time.perf_counter() - start_time) * 1000

    return MultimodalIngestionResult(
        ingestion_id=ingestion_id,
        images_processed=len(image_results),
        pdfs_processed=len(pdf_results),
        total_findings=sum(len(r.findings) for r in image_results),
        total_latency_ms=total_latency,
        image_results=image_results,
        pdf_results=pdf_results,
        errors=errors,
        provenance=provenance,
    )


def create_parsed_report_from_multimodal(result: MultimodalIngestionResult) -> ParsedReport:
    """
    Convert multimodal ingestion result to ParsedReport for compatibility
    with existing report interpretation pipeline.
    """
    text_blocks = []
    tables = []

    # Add image findings as text blocks
    for img_result in result.image_results:
        text_blocks.append(f"Image Analysis ({img_result.image_id}):")
        text_blocks.append(f"  Impression: {img_result.impression}")
        for finding in img_result.findings:
            text_blocks.append(f"  Finding: {finding}")
        if img_result.recommendations:
            text_blocks.append(f"  Recommendations: {', '.join(img_result.recommendations)}")
        text_blocks.append("")

    # Add PDF content
    for pdf_doc in result.pdf_results:
        text_blocks.append(f"PDF Document: {pdf_doc.filename}")
        text_blocks.append(pdf_doc.full_text)
        for page in pdf_doc.pages:
            for table in page.tables:
                tables.append(table)
        text_blocks.append("")

    full_text = "\n".join(text_blocks)

    return ParsedReport(
        raw_text=full_text,
        text_blocks=text_blocks,
        tables=tables,
        format="multimodal",
        raw_bytes_hash=result.ingestion_id,
        images_meta=[{
            "image_id": r.image_id,
            "modality": r.modality.value,
            "findings_count": len(r.findings),
            "model_used": r.model_used,
        } for r in result.image_results],
        needs_review=len(result.errors) > 0,
    )