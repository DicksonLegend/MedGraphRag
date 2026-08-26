"""
MedGraphRAG Backend — Multimodal Schemas
=========================================
Pydantic data models for multimodal medical data processing:
- Medical images (X-ray, CT, MRI, pathology slides)
- PDF document parsing with vision-language models
- Structured output for integration with retrieval pipeline
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class ImageModality(str, Enum):
    """Medical imaging modality types."""
    XRAY = "xray"
    CT = "ct"
    MRI = "mri"
    ULTRASOUND = "ultrasound"
    PATHOLOGY = "pathology"
    DERMATOLOGY = "dermatology"
    OCT = "oct"
    FUNDUS = "fundus"
    ENDOSCOPY = "endoscopy"
    UNKNOWN = "unknown"


class ImageOrientation(str, Enum):
    """Image orientation/view for radiology."""
    AP = "AP"  # Anteroposterior
    PA = "PA"  # Posteroanterior
    LATERAL = "LATERAL"
    OBLIQUE = "OBLIQUE"
    AXIAL = "AXIAL"
    CORONAL = "CORONAL"
    SAGITTAL = "SAGITTAL"
    UNKNOWN = "UNKNOWN"


class VisualFinding(BaseModel):
    """Detailed visual finding with confidence and clinical negation state."""
    label: str = Field(..., description="Pathology finding label")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Softmax confidence probability (0..1)")
    negated: bool = Field(False, description="True if finding is absent/negated")
    location: Optional[str] = Field(None, description="Anatomical location if localized")
    severity: Optional[str] = Field(None, description="Severity grade (mild/moderate/severe)")
    auc_reference: Optional[float] = Field(None, description="BiomedCLIP benchmark validation AUC")


class KnowledgeGraphPath(BaseModel):
    """Knowledge graph linkage from report_graph Kùzu DB."""
    source_image_id: str
    finding_label: str
    finding_negated: bool
    matched_reports: List[Dict[str, Any]] = Field(default_factory=list, description="Cross-linked reports from OpenI")


class MedicalImage(BaseModel):
    """Medical image with metadata for VLM processing."""
    image_id: str = Field(..., description="Unique identifier for this image")
    filename: str = Field(..., description="Original filename")
    modality: ImageModality = Field(default=ImageModality.UNKNOWN, description="Imaging modality")
    orientation: ImageOrientation = Field(default=ImageOrientation.UNKNOWN, description="Image orientation/view")
    body_part: Optional[str] = Field(None, description="Anatomical region imaged")
    patient_id: Optional[str] = Field(None, description="Patient identifier if available")
    study_id: Optional[str] = Field(None, description="Study/accession number")
    series_id: Optional[str] = Field(None, description="Series number")
    instance_id: Optional[str] = Field(None, description="Instance number")
    acquisition_date: Optional[str] = Field(None, description="Image acquisition date")
    pixel_spacing: Optional[List[float]] = Field(None, description="Pixel spacing in mm [row, col]")
    image_shape: Optional[List[int]] = Field(None, description="Image dimensions [H, W, C]")
    file_bytes_hash: str = Field(..., description="SHA-256 hash of original image bytes")
    image_bytes: Optional[bytes] = Field(None, description="Raw image bytes (not stored in DB)")
    preview_bytes: Optional[bytes] = Field(None, description="8-bit PNG preview bytes")
    needs_review: bool = Field(False, description="True if image quality/confidence is low")


class ImageAnalysisResult(BaseModel):
    """Result of VLM/ML analysis on a medical image."""
    image_id: str
    filename: str = ""
    modality: ImageModality = ImageModality.XRAY
    orientation: ImageOrientation = ImageOrientation.UNKNOWN
    body_part: Optional[str] = "Chest"
    mode: str = Field("triage", description="'triage' (fast zero-shot) or 'full' (generative VLM)")
    findings: List[str] = Field(default_factory=list, description="List of detected findings")
    findings_detailed: List[VisualFinding] = Field(default_factory=list, description="Detailed findings with locations & confidences")
    impression: str = Field("", description="Overall radiological impression/summary")
    recommendations: List[str] = Field(default_factory=list, description="Follow-up recommendations")
    confidence_scores: Dict[str, float] = Field(default_factory=dict, description="Per-finding confidence scores")
    refusal_tier: str = Field("ANSWERED", description="ANSWERED, HEDGED, or REFUSED")
    has_graph_links: bool = Field(False, description="True if matched in report_graph/kuzu.db")
    graph_paths: List[KnowledgeGraphPath] = Field(default_factory=list, description="Linked knowledge graph paths")
    graph_notice: Optional[str] = Field(None, description="Notice regarding graph links")
    preview_url: str = Field("", description="URL endpoint to fetch 8-bit PNG preview")
    processing_time_ms: float = Field(0.0, description="Processing latency in milliseconds")
    model_used: str = Field("", description="Model identifier used for analysis")
    provenance: List[str] = Field(default_factory=list, description="Provenance for findings")
    created_at: str = Field("", description="ISO timestamp")


class PDFDocument(BaseModel):
    """PDF document with extracted content and structure."""
    document_id: str = Field(..., description="Unique identifier for this document")
    filename: str = Field(..., description="Original filename")
    file_bytes_hash: str = Field(..., description="SHA-256 hash of original PDF bytes")
    page_count: int = Field(0, description="Number of pages in PDF")
    pages: List["PDFPage"] = Field(default_factory=list, description="Per-page content")
    full_text: str = Field("", description="Concatenated full text from all pages")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="PDF metadata (author, creator, etc.)")
    needs_review: bool = Field(False, description="True if parsing had issues")


class PDFPage(BaseModel):
    """Single page from a PDF document."""
    page_number: int = Field(..., description="1-indexed page number")
    text: str = Field("", description="Extracted text from page")
    tables: List[List[List[str]]] = Field(default_factory=list, description="Extracted tables")
    images: List["PDFImage"] = Field(default_factory=list, description="Embedded images")
    visual_elements: List[Dict[str, Any]] = Field(default_factory=list, description="Layout elements from VLM")


class PDFImage(BaseModel):
    """Image embedded within a PDF page."""
    image_index: int = Field(..., description="Index of image on page")
    xref: int = Field(0, description="PyMuPDF xref number")
    width: int = Field(0, description="Image width in pixels")
    height: int = Field(0, description="Image height in pixels")
    colorspace: str = Field("", description="Color space")
    image_bytes: Optional[bytes] = Field(None, description="Raw image bytes")
    image_bytes_hash: str = Field("", description="SHA-256 hash of image bytes")
    analysis: Optional[ImageAnalysisResult] = Field(None, description="VLM analysis if processed")


class MultimodalIngestionResult(BaseModel):
    """Complete result of multimodal ingestion pipeline."""
    ingestion_id: str = Field(..., description="Unique ingestion run identifier")
    images_processed: int = Field(0)
    pdfs_processed: int = Field(0)
    total_findings: int = Field(0)
    total_latency_ms: float = Field(0.0)
    image_results: List[ImageAnalysisResult] = Field(default_factory=list)
    pdf_results: List[PDFDocument] = Field(default_factory=list)
    errors: List[Dict[str, str]] = Field(default_factory=list)
    provenance: List[str] = Field(default_factory=list)


# Forward references
PDFDocument.model_rebuild()
PDFPage.model_rebuild()
PDFImage.model_rebuild()