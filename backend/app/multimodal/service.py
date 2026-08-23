"""
MedGraphRAG Backend — Multimodal Service
=========================================
Orchestrates multimodal ingestion, analysis, and integration with the
existing report interpretation and retrieval pipelines.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.config import settings
from app.core.report.service import ReportInterpretationService
from app.core.report.schemas import ReportResult
from app.multimodal.parser import ingest_multimodal_files, create_parsed_report_from_multimodal
from app.multimodal.schemas import (
    ImageAnalysisResult,
    MedicalImage,
    MultimodalIngestionResult,
    PDFDocument,
)

logger = logging.getLogger(__name__)


class MultimodalService:
    """
    Service for processing multimodal medical data (images, PDFs) and
    integrating with the MedGraphRAG pipeline.
    """

    def __init__(self) -> None:
        self.report_service = ReportInterpretationService()

    def process_multimodal_files(
        self,
        file_paths: List[Union[str, Path]],
        user_id: str = "default_user",
        destination: str = "private",
        analyze_images: bool = True,
        run_full_interpretation: bool = True,
    ) -> Dict[str, Any]:
        """
        Process multimodal files through the complete pipeline:
        1. Ingest and parse files (images, PDFs)
        2. Run VLM analysis on images
        3. Convert to ParsedReport format
        4. Run full report interpretation (lab extraction, normalization, assessment, explanations)
        5. Store in private encrypted storage

        Parameters
        ----------
        file_paths : List of file paths to process
        user_id : User identifier
        destination : Storage destination
        analyze_images : Whether to run VLM on images
        run_full_interpretation : Whether to run Stages B-F of report pipeline

        Returns
        -------
        Dict with ingestion results and optionally full interpretation results
        """
        start_time = time.perf_counter()

        logger.info("MultimodalService: Processing %d files for user %s", len(file_paths), user_id)

        # Stage 1: Multimodal Ingestion + VLM Analysis
        ingestion_result = ingest_multimodal_files(
            file_paths=file_paths,
            user_id=user_id,
            destination=destination,
            analyze_images=analyze_images,
        )

        # Stage 2: Convert to ParsedReport for compatibility
        parsed_report = create_parsed_report_from_multimodal(ingestion_result)

        result = {
            "ingestion": ingestion_result,
            "parsed_report": parsed_report,
        }

        # Stage 3: Full Report Interpretation (optional)
        if run_full_interpretation and (ingestion_result.image_results or ingestion_result.pdf_results):
            try:
                logger.info("Running full report interpretation on multimodal content...")

                # We need to create a "file" for the report service
                # Since we have parsed content, we'll use the report service directly
                # with the extracted content

                # For now, we can process the parsed_report through the existing pipeline
                # by converting it to the format expected by ReportInterpretationService
                # The service expects file_bytes - we'll use the parsed text as bytes

                combined_text = parsed_report.raw_text.encode("utf-8")

                # We need to adapt - the report service expects raw file bytes
                # For multimodal, we have already extracted content
                # Let's run the lab value extraction etc. on the combined text

                # For now, return the ingestion result with parsed report
                # Full integration would require modifying ReportInterpretationService
                # to accept pre-parsed content

                result["interpretation"] = {
                    "status": "parsed_only",
                    "message": "Full interpretation pipeline integration pending",
                    "lab_values_extracted": 0,
                    "assessments_generated": 0,
                }

            except Exception as e:
                logger.error("Full interpretation failed: %s", e)
                result["interpretation"] = {
                    "status": "error",
                    "error": str(e),
                }

        total_latency = (time.perf_counter() - start_time) * 1000
        logger.info("MultimodalService complete in %.1f ms", total_latency)

        return result

    def process_single_image(
        self,
        file_path: Union[str, Path],
        user_id: str = "default_user",
        custom_prompt: Optional[str] = None,
    ) -> ImageAnalysisResult:
        """
        Process a single medical image with VLM analysis.

        Parameters
        ----------
        file_path : Path to image file
        user_id : User identifier
        custom_prompt : Optional custom prompt for VLM

        Returns
        -------
        ImageAnalysisResult with findings and analysis
        """
        from app.multimodal.parser import (
            load_standard_image,
            load_dicom_image,
            detect_image_modality,
            detect_orientation,
            compute_file_hash,
            analyze_medical_image_with_vlm,
        )

        path = Path(file_path)
        file_bytes = path.read_bytes()
        file_hash = compute_file_hash(file_bytes)
        ext = path.suffix.lower()

        if ext in {".dcm", ".dicom"}:
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
        else:
            pil_image = load_standard_image(file_bytes)
            modality = detect_image_modality(path.name, pil_image)
            orientation = detect_orientation(path.name)

            medical_image = MedicalImage(
                image_id=file_hash[:16],
                filename=path.name,
                modality=modality,
                orientation=orientation,
                image_shape=[pil_image.height, pil_image.width, 3],
                file_bytes_hash=file_hash,
                image_bytes=file_bytes,
            )

        analysis = analyze_medical_image_with_vlm(medical_image, prompt=custom_prompt)
        return analysis

    def process_single_pdf(
        self,
        file_path: Union[str, Path],
        analyze_embedded_images: bool = True,
    ) -> PDFDocument:
        """
        Process a single PDF document, extracting text, tables, and embedded images.

        Parameters
        ----------
        file_path : Path to PDF file
        analyze_embedded_images : Whether to run VLM on embedded images

        Returns
        -------
        PDFDocument with all extracted content
        """
        from app.multimodal.parser import parse_pdf_with_images

        path = Path(file_path)
        file_bytes = path.read_bytes()
        pdf_doc = parse_pdf_with_images(file_bytes, path.name)

        if analyze_embedded_images:
            import io
            from PIL import Image
            from app.multimodal.parser import compute_file_hash, analyze_medical_image_with_vlm

            for page in pdf_doc.pages:
                for pdf_img in page.images:
                    if pdf_img.image_bytes:
                        try:
                            pil_img = Image.open(io.BytesIO(pdf_img.image_bytes))
                            pdf_img_hash = compute_file_hash(pdf_img.image_bytes)

                            from app.multimodal.schemas import MedicalImage, ImageModality

                            med_img = MedicalImage(
                                image_id=f"{pdf_doc.document_id}_p{page.page_number}_img{pdf_img.image_index}",
                                filename=f"{path.name}_p{page.page_number}_img{pdf_img.image_index}",
                                modality=ImageModality.UNKNOWN,
                                file_bytes_hash=pdf_img_hash,
                                image_bytes=pdf_img.image_bytes,
                                image_shape=[pil_img.height, pil_img.width, 3],
                            )
                            analysis = analyze_medical_image_with_vlm(med_img)
                            pdf_img.analysis = analysis
                        except Exception as e:
                            logger.warning("Failed to analyze embedded image in PDF %s: %s", path.name, e)

        return pdf_doc

    def integrate_with_retrieval(
        self,
        ingestion_result: MultimodalIngestionResult,
        query: str,
    ) -> Dict[str, Any]:
        """
        Integrate multimodal findings with the hybrid retrieval pipeline.

        This allows multimodal content to be searched alongside the global
        knowledge base via the existing retrieval infrastructure.

        Parameters
        ----------
        ingestion_result : Result from multimodal ingestion
        query : User query to search for

        Returns
        -------
        Dict with retrieval results incorporating multimodal content
        """
        # TODO: This would require indexing multimodal content into FAISS/Kuzu
        # For now, return a placeholder structure

        return {
            "status": "not_implemented",
            "message": "Multimodal retrieval integration requires indexing pipeline",
            "multimodal_content_available": {
                "images": len(ingestion_result.image_results),
                "pdfs": len(ingestion_result.pdf_results),
                "total_findings": ingestion_result.total_findings,
            },
        }


# ---------------------------------------------------------------------------
# Convenience functions for API route integration
# ---------------------------------------------------------------------------

def process_uploaded_files(
    file_bytes_list: List[bytes],
    filenames: List[str],
    user_id: str = "default_user",
    destination: str = "private",
) -> Dict[str, Any]:
    """
    Process uploaded file bytes directly (for API route integration).

    Parameters
    ----------
    file_bytes_list : List of file bytes
    filenames : Corresponding filenames
    user_id : User identifier
    destination : Storage destination

    Returns
    -------
    Dict with processing results
    """
    import tempfile
    import os

    service = MultimodalService()

    # Write bytes to temp files for processing
    temp_paths = []
    try:
        for i, (file_bytes, filename) in enumerate(zip(file_bytes_list, filenames)):
            ext = Path(filename).suffix
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(file_bytes)
                temp_paths.append(tmp.name)

        result = service.process_multimodal_files(
            file_paths=temp_paths,
            user_id=user_id,
            destination=destination,
        )
        return result
    finally:
        # Cleanup temp files
        for tmp_path in temp_paths:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass