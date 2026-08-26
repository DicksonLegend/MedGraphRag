"""
MedGraphRAG Backend — Multimodal API Routes
============================================
FastAPI routes for medical imaging analysis, DICOM/PNG previews, and scan storage:
- GET  /multimodal/status             - Service status & capabilities
- POST /multimodal/analyze-image      - Triage / Full VLM analysis on single image
- GET  /multimodal/preview/{image_id} - 8-bit PNG preview image (owner-only)
- GET  /multimodal/scans              - List authenticated user's private scans
- DELETE /multimodal/scans/{image_id} - Purge scan from private store
- POST /multimodal/ingest             - Batch file ingest
- POST /multimodal/parse-pdf          - PDF document parser
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.config import settings
from app.multimodal.parser import (
    DICOM_EXTENSIONS,
    IMAGE_EXTENSIONS,
    PDF_EXTENSIONS,
    Qwen2VLEngine,
    parse_pdf_with_images,
)
from app.multimodal.schemas import (
    ImageAnalysisResult,
    ImageModality,
    MultimodalIngestionResult,
    PDFDocument,
)
from app.multimodal.service import MultimodalService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/multimodal", tags=["Multimodal Processing"])

_service: Optional[MultimodalService] = None


def get_multimodal_service() -> MultimodalService:
    global _service
    if _service is None:
        _service = MultimodalService()
    return _service


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

from app.api.deps import get_current_user, get_current_user_optional


@router.get("/status")
async def multimodal_status(
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
) -> Dict[str, Any]:
    """Get multimodal service capabilities and engine health (requires auth in non-dev)."""
    is_dev = settings.app_env.lower() in ("dev", "development", "local", "test")
    if not is_dev and current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to view multimodal service status.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    vlm_available = False
    vlm_model = "Qwen2-VL-2B-Instruct" if not is_dev else "Qwen2-VL-2B-Instruct-Q4_K_M (CPU, 4 threads)"
    try:
        from app.multimodal.parser import QWEN2_VL_GGUF, QWEN2_VL_MMPROJ
        if QWEN2_VL_GGUF.exists() and QWEN2_VL_MMPROJ.exists():
            vlm_available = True
    except Exception:
        pass

    dicom_available = False
    try:
        import pydicom
        dicom_available = True
    except ImportError:
        pass

    return {
        "service": "multimodal",
        "version": "1.0.0",
        "capabilities": {
            "image_formats": ["png", "jpg", "jpeg", "tiff", "bmp", "webp", "dcm", "dicom"],
            "dicom_support": dicom_available,
            "pdf_support": True,
            "biomedclip_triage": True,
            "vlm_analysis": vlm_available,
            "vlm_model": vlm_model,
            "report_graph_links": True,
            "private_encryption": "AES-256-GCM",
        },
        "supported_modalities": [m.value for m in ImageModality],
    }


@router.post("/analyze-image", response_model=ImageAnalysisResult)
async def analyze_image(
    file: UploadFile = File(..., description="Medical image file (.png, .jpg, .dcm)"),
    mode: str = Form("triage", description="'triage' (fast zero-shot) or 'full' (generative VLM)"),
    custom_prompt: Optional[str] = Form(None, description="Custom prompt for generative interpretation"),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> ImageAnalysisResult:
    """
    Analyze uploaded medical scan:
    - Mode 'triage': Runs BiomedCLIP zero-shot pathology scoring (~200ms) and checks report graph.
    - Mode 'full': Runs full generative Qwen2-VL-2B interpretation on CPU.
    - Stores scan and 8-bit PNG preview into private_store/{user_id}/scans/{image_id}/.
    """
    user_id = current_user["user_id"]
    filename = file.filename or "scan.png"
    ext = "." + filename.split(".")[-1].lower()

    if ext not in IMAGE_EXTENSIONS and ext not in DICOM_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported image format '{ext}'. Allowed formats: PNG, JPG, JPEG, TIFF, BMP, DICOM (.dcm)",
        )

    file_bytes = await file.read()
    if len(file_bytes) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Scan file size exceeds maximum limit of {settings.max_upload_mb} MB.",
        )

    # Magic byte validation (F-06)
    from app.core.security.validation import validate_file_magic_bytes
    validate_file_magic_bytes(file_bytes, filename)

    service = get_multimodal_service()
    result = service.process_and_store_image(
        file_bytes=file_bytes,
        filename=filename,
        user_id=user_id,
        mode=mode,
        custom_prompt=custom_prompt,
    )
    return result


from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path as FastApiPath,
    Response,
    UploadFile,
    status,
)


@router.get("/preview/{image_id}")
async def get_preview(
    image_id: str = FastApiPath(..., pattern=r"^[A-Za-z0-9._-]{1,80}$", description="Alphanumeric image identifier"),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Response:
    """
    Serve downscaled 8-bit PNG preview for a scan.
    Owner-only authorization enforced via Bearer JWT.
    """
    user_id = current_user["user_id"]
    service = get_multimodal_service()
    preview_bytes = service.get_image_preview(user_id=user_id, image_id=image_id)
    return Response(content=preview_bytes, media_type="image/png")


@router.get("/scans", response_model=List[ImageAnalysisResult])
async def list_scans(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> List[ImageAnalysisResult]:
    """List all stored medical scans and their analysis records for the authenticated user."""
    user_id = current_user["user_id"]
    service = get_multimodal_service()
    return service.list_user_scans(user_id=user_id)


@router.delete("/scans/{image_id}")
async def delete_scan(
    image_id: str = FastApiPath(..., pattern=r"^[A-Za-z0-9._-]{1,80}$", description="Alphanumeric image identifier"),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Purge a stored scan and its encrypted metadata from the user's private store."""
    user_id = current_user["user_id"]
    service = get_multimodal_service()
    deleted = service.purge_user_scan(user_id=user_id, image_id=image_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan {image_id} not found in your private storage.",
        )
    return {"status": "purged", "image_id": image_id}


@router.post("/parse-pdf", response_model=PDFDocument)
async def parse_pdf(
    file: UploadFile = File(..., description="PDF document to parse"),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> PDFDocument:
    """Extract text, tables, and embedded images from PDF document."""
    content = await file.read()
    filename = file.filename or "document.pdf"
    from app.core.security.validation import validate_file_magic_bytes, validate_pdf_safety_caps
    validate_file_magic_bytes(content, filename)
    validate_pdf_safety_caps(content, max_pages=200)
    return parse_pdf_with_images(content, filename)