"""
MedGraphRAG Backend — Multimodal API Routes
============================================
FastAPI routes for multimodal medical data processing:
- POST /multimodal/ingest - Ingest images and PDFs
- POST /multimodal/analyze-image - Analyze single image with VLM
- POST /multimodal/parse-pdf - Parse PDF with embedded images
- GET /multimodal/status - Service status
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.multimodal.service import MultimodalService, process_uploaded_files

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/multimodal", tags=["Multimodal Processing"])

# Service instance
_multimodal_service: Optional[MultimodalService] = None


def get_multimodal_service() -> MultimodalService:
    """Get or create MultimodalService singleton."""
    global _multimodal_service
    if _multimodal_service is None:
        _multimodal_service = MultimodalService()
    return _multimodal_service


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------

class MultimodalIngestRequest(BaseModel):
    """Request model for multimodal ingestion."""
    user_id: Optional[str] = Field(None, description="User ID (defaults to authenticated user)")
    destination: str = Field("private", description="Storage destination")
    analyze_images: bool = Field(True, description="Run VLM analysis on images")
    run_full_interpretation: bool = Field(True, description="Run full report interpretation pipeline")


class MultimodalIngestResponse(BaseModel):
    """Response model for multimodal ingestion."""
    ingestion_id: str
    images_processed: int
    pdfs_processed: int
    total_findings: int
    total_latency_ms: float
    image_results: List[Dict[str, Any]] = Field(default_factory=list)
    pdf_results: List[Dict[str, Any]] = Field(default_factory=list)
    errors: List[Dict[str, str]] = Field(default_factory=list)
    provenance: List[str] = Field(default_factory=list)
    interpretation: Optional[Dict[str, Any]] = None


class ImageAnalyzeRequest(BaseModel):
    """Request model for single image analysis."""
    custom_prompt: Optional[str] = Field(None, description="Custom prompt for VLM analysis")


class ImageAnalyzeResponse(BaseModel):
    """Response model for single image analysis."""
    image_id: str
    findings: List[str]
    findings_detailed: List[Dict[str, Any]]
    impression: str
    recommendations: List[str]
    confidence_scores: Dict[str, float]
    modality: str
    processing_time_ms: float
    model_used: str
    provenance: List[str]


class PDFParseResponse(BaseModel):
    """Response model for PDF parsing."""
    document_id: str
    filename: str
    file_bytes_hash: str
    page_count: int
    full_text: str
    metadata: Dict[str, Any]
    pages: List[Dict[str, Any]]
    needs_review: bool


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/ingest", response_model=MultimodalIngestResponse)
async def ingest_multimodal(
    files: List[UploadFile] = File(..., description="Image and/or PDF files to process"),
    user_id: Optional[str] = Form(None, description="User ID (defaults to authenticated user)"),
    destination: str = Form("private", description="Storage destination"),
    analyze_images: bool = Form(True, description="Run VLM analysis on images"),
    run_full_interpretation: bool = Form(True, description="Run full report interpretation"),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> MultimodalIngestResponse:
    """
    Ingest multimodal medical files (images, PDFs) for processing.

    Supports:
    - Medical images: PNG, JPG, JPEG, TIFF, BMP, WebP
    - DICOM: .dcm, .dicom
    - PDF documents with embedded images

    Files are processed through:
    1. Format-specific parsing (DICOM tags, PDF text/tables/images)
    2. Vision-Language Model analysis (medical findings, impressions)
    3. Optional full report interpretation pipeline (lab extraction, assessment)
    4. Private encrypted storage
    """
    # Use authenticated user if not specified
    effective_user_id = user_id or current_user["user_id"]

    # Validate destination access
    if destination != "global" and destination != effective_user_id and destination != f"private_store/{effective_user_id}":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to store in another user's private store.",
        )

    # Read file bytes
    file_bytes_list = []
    filenames = []

    for file in files:
        content = await file.read()
        file_bytes_list.append(content)
        filenames.append(file.filename or f"file_{len(file_bytes_list)}")

    logger.info("Multimodal ingest: %d files for user %s", len(files), effective_user_id)

    # Process files
    result = process_uploaded_files(
        file_bytes_list=file_bytes_list,
        filenames=filenames,
        user_id=effective_user_id,
        destination=destination,
    )

    # Convert to response model
    ingestion = result["ingestion"]
    response = MultimodalIngestResponse(
        ingestion_id=ingestion.ingestion_id,
        images_processed=ingestion.images_processed,
        pdfs_processed=ingestion.pdfs_processed,
        total_findings=ingestion.total_findings,
        total_latency_ms=ingestion.total_latency_ms,
        image_results=[
            {
                "image_id": r.image_id,
                "findings": r.findings,
                "findings_detailed": r.findings_detailed,
                "impression": r.impression,
                "recommendations": r.recommendations,
                "confidence_scores": r.confidence_scores,
                "modality": r.modality.value,
                "processing_time_ms": r.processing_time_ms,
                "model_used": r.model_used,
                "provenance": r.provenance,
            }
            for r in ingestion.image_results
        ],
        pdf_results=[
            {
                "document_id": r.document_id,
                "filename": r.filename,
                "file_bytes_hash": r.file_bytes_hash,
                "page_count": r.page_count,
                "full_text": r.full_text[:5000] + ("..." if len(r.full_text) > 5000 else ""),  # Truncate for response
                "metadata": r.metadata,
                "pages": [
                    {
                        "page_number": p.page_number,
                        "text_length": len(p.text),
                        "tables_count": len(p.tables),
                        "images_count": len(p.images),
                    }
                    for p in r.pages
                ],
                "needs_review": r.needs_review,
            }
            for r in ingestion.pdf_results
        ],
        errors=ingestion.errors,
        provenance=ingestion.provenance,
        interpretation=result.get("interpretation"),
    )

    return response


@router.post("/analyze-image", response_model=ImageAnalyzeResponse)
async def analyze_image(
    file: UploadFile = File(..., description="Medical image file to analyze"),
    custom_prompt: Optional[str] = Form(None, description="Custom VLM prompt"),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> ImageAnalyzeResponse:
    """
    Analyze a single medical image with Vision-Language Model.

    Returns structured findings, impression, and recommendations.
    """
    import tempfile
    import os

    content = await file.read()
    filename = file.filename or "image.png"

    # Write to temp file
    ext = Path(filename).suffix
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(content)
        temp_path = tmp.name

    try:
        service = get_multimodal_service()
        analysis = service.process_single_image(
            file_path=temp_path,
            user_id=current_user["user_id"],
            custom_prompt=custom_prompt,
        )

        return ImageAnalyzeResponse(
            image_id=analysis.image_id,
            findings=analysis.findings,
            findings_detailed=analysis.findings_detailed,
            impression=analysis.impression,
            recommendations=analysis.recommendations,
            confidence_scores=analysis.confidence_scores,
            modality=analysis.modality.value,
            processing_time_ms=analysis.processing_time_ms,
            model_used=analysis.model_used,
            provenance=analysis.provenance,
        )
    finally:
        try:
            os.unlink(temp_path)
        except Exception:
            pass


@router.post("/parse-pdf", response_model=PDFParseResponse)
async def parse_pdf(
    file: UploadFile = File(..., description="PDF document to parse"),
    analyze_embedded_images: bool = Form(True, description="Analyze embedded images with VLM"),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> PDFParseResponse:
    """
    Parse a PDF document, extracting text, tables, and embedded images.

    Optionally runs VLM analysis on embedded medical images.
    """
    import tempfile
    import os

    content = await file.read()
    filename = file.filename or "document.pdf"

    # Write to temp file
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        temp_path = tmp.name

    try:
        service = get_multimodal_service()
        pdf_doc = service.process_single_pdf(
            file_path=temp_path,
            analyze_embedded_images=analyze_embedded_images,
        )

        return PDFParseResponse(
            document_id=pdf_doc.document_id,
            filename=pdf_doc.filename,
            file_bytes_hash=pdf_doc.file_bytes_hash,
            page_count=pdf_doc.page_count,
            full_text=pdf_doc.full_text[:10000] + ("..." if len(pdf_doc.full_text) > 10000 else ""),
            metadata=pdf_doc.metadata,
            pages=[
                {
                    "page_number": p.page_number,
                    "text": p.text[:2000] + ("..." if len(p.text) > 2000 else ""),
                    "tables": p.tables,
                    "images": [
                        {
                            "image_index": img.image_index,
                            "width": img.width,
                            "height": img.height,
                            "colorspace": img.colorspace,
                            "image_bytes_hash": img.image_bytes_hash,
                            "analysis": {
                                "image_id": img.analysis.image_id,
                                "findings": img.analysis.findings,
                                "impression": img.analysis.impression,
                            } if img.analysis else None,
                        }
                        for img in p.images
                    ],
                    "visual_elements": p.visual_elements,
                }
                for p in pdf_doc.pages
            ],
            needs_review=pdf_doc.needs_review,
        )
    finally:
        try:
            os.unlink(temp_path)
        except Exception:
            pass


@router.get("/status")
async def multimodal_status() -> Dict[str, Any]:
    """
    Get multimodal service status and capabilities.
    """
    # Check available backends
    vlm_available = False
    vlm_model = "Not configured"

    try:
        # Check if VLM is configured
        from app.config import settings
        if hasattr(settings, 'vlm_model_path') and settings.vlm_model_path:
            vlm_available = True
            vlm_model = settings.vlm_model_path
    except Exception:
        pass

    ocr_available = False
    try:
        import easyocr
        ocr_available = True
    except ImportError:
        try:
            import pytesseract
            ocr_available = True
        except ImportError:
            pass

    dicom_available = False
    try:
        import pydicom
        dicom_available = True
    except ImportError:
        pass

    return {
        "service": "multimodal",
        "version": "0.1.0",
        "capabilities": {
            "image_formats": ["png", "jpg", "jpeg", "tiff", "bmp", "webp"],
            "dicom_support": dicom_available,
            "pdf_support": True,
            "vlm_analysis": vlm_available,
            "vlm_model": vlm_model,
            "ocr_support": ocr_available,
            "embedded_image_analysis": vlm_available,
        },
        "supported_modalities": [m.value for m in __import__("app.multimodal.schemas", fromlist=["ImageModality"]).ImageModality],
    }