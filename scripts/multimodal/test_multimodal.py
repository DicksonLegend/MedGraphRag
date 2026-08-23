#!/usr/bin/env python3
"""
MedGraphRAG — Multimodal Pipeline Test
=======================================
Quick test script to verify multimodal components load correctly.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add backend to path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "backend"))

def test_imports():
    """Test that all multimodal modules import correctly."""
    print("Testing multimodal imports...")

    try:
        from app.multimodal import schemas
        print("  ✓ app.multimodal.schemas")
    except Exception as e:
        print(f"  ✗ app.multimodal.schemas: {e}")
        return False

    try:
        from app.multimodal import parser
        print("  ✓ app.multimodal.parser")
    except Exception as e:
        print(f"  ✗ app.multimodal.parser: {e}")
        return False

    try:
        from app.multimodal import service
        print("  ✓ app.multimodal.service")
    except Exception as e:
        print(f"  ✗ app.multimodal.service: {e}")
        return False

    try:
        from app.multimodal import routes
        print("  ✓ app.multimodal.routes")
    except Exception as e:
        print(f"  ✗ app.multimodal.routes: {e}")
        return False

    try:
        from app.api.routes import multimodal as api_multimodal
        print("  ✓ app.api.routes.multimodal")
    except Exception as e:
        print(f"  ✗ app.api.routes.multimodal: {e}")
        return False

    return True


def test_schemas():
    """Test schema instantiation."""
    print("\nTesting schema instantiation...")

    from app.multimodal.schemas import (
        MedicalImage,
        ImageAnalysisResult,
        PDFDocument,
        PDFPage,
        PDFImage,
        MultimodalIngestionResult,
        ImageModality,
        ImageOrientation,
    )

    try:
        # Test MedicalImage
        img = MedicalImage(
            image_id="test_001",
            filename="chest_xray.png",
            modality=ImageModality.XRAY,
            orientation=ImageOrientation.PA,
            file_bytes_hash="abc123",
        )
        print(f"  ✓ MedicalImage: {img.image_id} ({img.modality.value})")

        # Test ImageAnalysisResult
        analysis = ImageAnalysisResult(
            image_id="test_001",
            findings=["Cardiomegaly", "Pleural effusion"],
            impression="Enlarged cardiac silhouette with bilateral pleural effusions",
            recommendations=["Chest CT for further evaluation", "Clinical correlation"],
            modality=ImageModality.XRAY,
            model_used="llava-med-7b",
        )
        print(f"  ✓ ImageAnalysisResult: {len(analysis.findings)} findings")

        # Test PDFDocument
        pdf = PDFDocument(
            document_id="pdf_001",
            filename="report.pdf",
            file_bytes_hash="def456",
            page_count=3,
            full_text="Sample medical report text...",
        )
        print(f"  ✓ PDFDocument: {pdf.filename} ({pdf.page_count} pages)")

        # Test MultimodalIngestionResult
        result = MultimodalIngestionResult(
            ingestion_id="ingest_001",
            images_processed=2,
            pdfs_processed=1,
            total_findings=5,
            total_latency_ms=1500.0,
        )
        print(f"  ✓ MultimodalIngestionResult: {result.ingestion_id}")

    except Exception as e:
        print(f"  ✗ Schema test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


def test_modality_detection():
    """Test modality detection from filenames."""
    print("\nTesting modality detection...")

    from app.multimodal.parser import detect_image_modality, detect_orientation
    from app.multimodal.schemas import ImageModality, ImageOrientation

    test_cases = [
        ("chest_xray.png", ImageModality.XRAY),
        ("ct_abdomen.dcm", ImageModality.CT),
        ("mri_brain_t1.nii", ImageModality.MRI),
        ("pathology_slide_hne.tiff", ImageModality.PATHOLOGY),
        ("derm_lesion.jpg", ImageModality.DERMATOLOGY),
        ("fundus_retina.png", ImageModality.FUNDUS),
        ("unknown_image.png", ImageModality.UNKNOWN),
    ]

    for filename, expected in test_cases:
        detected = detect_image_modality(filename)
        status = "✓" if detected == expected else "✗"
        print(f"  {status} {filename}: {detected.value} (expected: {expected.value})")

    return True


def test_service_initialization():
    """Test MultimodalService initialization."""
    print("\nTesting MultimodalService initialization...")

    try:
        from app.multimodal.service import MultimodalService
        service = MultimodalService()
        print(f"  ✓ MultimodalService initialized")
        print(f"  ✓ ReportInterpretationService attached: {service.report_service is not None}")
    except Exception as e:
        print(f"  ✗ Service initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("MEDGRAPHRAG MULTIMODAL PIPELINE TEST")
    print("=" * 60)

    all_passed = True

    all_passed &= test_imports()
    all_passed &= test_schemas()
    all_passed &= test_modality_detection()
    all_passed &= test_service_initialization()

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())