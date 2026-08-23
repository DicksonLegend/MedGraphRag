#!/usr/bin/env python3
"""
MedGraphRAG — Multimodal Ingestion Script
==========================================
Command-line tool for ingesting medical images and PDFs into the MedGraphRAG pipeline.

Usage:
    python -m scripts.multimodal.ingest_multimodal --files image1.png image2.dcm report.pdf --user demo_user
    python -m scripts.multimodal.ingest_multimodal --dir data/multimodal/images --user demo_user --analyze
    python -m scripts.multimodal.ingest_multimodal --files chest_xray.png --user demo_user --prompt "Focus on lung fields and cardiac silhouette"
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import List

# Add backend to path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "backend"))

from app.multimodal.service import MultimodalService
from app.multimodal.schemas import MultimodalIngestionResult

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def collect_files(
    files: List[str],
    directories: List[str],
    extensions: List[str],
    recursive: bool,
) -> List[Path]:
    """Collect file paths from explicit files and directories."""
    collected: List[Path] = []

    # Add explicit files
    for f in files:
        path = Path(f)
        if path.exists():
            collected.append(path)
        else:
            logger.warning("File not found: %s", f)

    # Add files from directories
    for d in directories:
        dir_path = Path(d)
        if not dir_path.exists():
            logger.warning("Directory not found: %s", d)
            continue

        if recursive:
            pattern = "**/*"
        else:
            pattern = "*"

        for ext in extensions:
            for file_path in dir_path.glob(f"{pattern}{ext}"):
                if file_path.is_file():
                    collected.append(file_path)

    # Deduplicate
    unique = []
    seen = set()
    for p in collected:
        if p not in seen:
            seen.add(p)
            unique.append(p)

    return unique


def save_results(result: MultimodalIngestionResult, output_path: Path) -> None:
    """Save ingestion results to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to serializable dict
    result_dict = {
        "ingestion_id": result.ingestion_id,
        "images_processed": result.images_processed,
        "pdfs_processed": result.pdfs_processed,
        "total_findings": result.total_findings,
        "total_latency_ms": result.total_latency_ms,
        "image_results": [
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
            for r in result.image_results
        ],
        "pdf_results": [
            {
                "document_id": r.document_id,
                "filename": r.filename,
                "file_bytes_hash": r.file_bytes_hash,
                "page_count": r.page_count,
                "full_text": r.full_text,
                "metadata": r.metadata,
                "pages": [
                    {
                        "page_number": p.page_number,
                        "text": p.text,
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
                    for p in r.pages
                ],
                "needs_review": r.needs_review,
            }
            for r in result.pdf_results
        ],
        "errors": result.errors,
        "provenance": result.provenance,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result_dict, f, indent=2, ensure_ascii=False)

    logger.info("Results saved to: %s", output_path)


def main():
    parser = argparse.ArgumentParser(
        description="MedGraphRAG Multimodal Ingestion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Ingest specific files
  python -m scripts.multimodal.ingest_multimodal --files chest_xray.png ct_scan.dcm lab_report.pdf --user demo_user

  # Ingest all images from directory
  python -m scripts.multimodal.ingest_multimodal --dir data/multimodal/images --user demo_user --analyze

  # Ingest with custom VLM prompt
  python -m scripts.multimodal.ingest_multimodal --files mammogram.png --user demo_user --prompt "Assess breast density and any suspicious masses"

  # Dry run (no VLM analysis)
  python -m scripts.multimodal.ingest_multimodal --files image.png --user demo_user --no-analyze
        """
    )

    # Input options
    parser.add_argument(
        "--files", "-f",
        nargs="+",
        default=[],
        help="Explicit file paths to ingest"
    )
    parser.add_argument(
        "--dir", "-d",
        nargs="+",
        default=[],
        help="Directories to scan for files"
    )
    parser.add_argument(
        "--extensions", "-e",
        nargs="+",
        default=[".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp", ".dcm", ".dicom", ".pdf"],
        help="File extensions to include (when using --dir)"
    )
    parser.add_argument(
        "--recursive", "-r",
        action="store_true",
        default=True,
        help="Recursively scan directories"
    )

    # Processing options
    parser.add_argument(
        "--user", "-u",
        default="demo_user",
        help="User ID for private storage"
    )
    parser.add_argument(
        "--destination",
        default="private",
        choices=["global", "private"],
        help="Storage destination"
    )
    parser.add_argument(
        "--analyze", "-a",
        action="store_true",
        default=True,
        help="Run VLM analysis on images"
    )
    parser.add_argument(
        "--no-analyze",
        action="store_false",
        dest="analyze",
        help="Skip VLM analysis (faster, parsing only)"
    )
    parser.add_argument(
        "--prompt", "-p",
        default=None,
        help="Custom prompt for VLM analysis"
    )

    # Output options
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output JSON file path (default: evaluations/multimodal/ingest_<timestamp>.json)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Collect files
    logger.info("Collecting files...")
    file_paths = collect_files(
        files=args.files,
        directories=args.dir,
        extensions=args.extensions,
        recursive=args.recursive,
    )

    if not file_paths:
        logger.error("No files found to process!")
        sys.exit(1)

    logger.info("Found %d files to process", len(file_paths))
    for fp in file_paths:
        logger.info("  %s", fp)

    # Process files
    logger.info("Starting multimodal ingestion...")
    start_time = time.perf_counter()

    service = MultimodalService()
    result = service.process_multimodal_files(
        file_paths=file_paths,
        user_id=args.user,
        destination=args.destination,
        analyze_images=args.analyze,
        run_full_interpretation=True,
    )

    elapsed = (time.perf_counter() - start_time) * 1000

    # Display summary
    ingestion = result["ingestion"]
    print("\n" + "=" * 70)
    print("MULTIMODAL INGESTION COMPLETE")
    print("=" * 70)
    print(f"Ingestion ID : {ingestion.ingestion_id}")
    print(f"Images       : {ingestion.images_processed}")
    print(f"PDFs         : {ingestion.pdfs_processed}")
    print(f"Total findings: {ingestion.total_findings}")
    print(f"Errors       : {len(ingestion.errors)}")
    print(f"Total latency: {elapsed:.1f} ms")
    print("=" * 70)

    if ingestion.image_results:
        print("\nIMAGE ANALYSIS RESULTS:")
        for img in ingestion.image_results:
            print(f"  [{img.image_id}] {img.modality.value} - {len(img.findings)} findings")
            for finding in img.findings[:3]:  # Show first 3 findings
                print(f"    - {finding}")
            if len(img.findings) > 3:
                print(f"    ... and {len(img.findings) - 3} more")
            print(f"    Impression: {img.impression[:100]}...")

    if ingestion.pdf_results:
        print("\nPDF PARSING RESULTS:")
        for pdf in ingestion.pdf_results:
            print(f"  [{pdf.document_id}] {pdf.filename} - {pdf.page_count} pages")
            print(f"    Text length: {len(pdf.full_text)} chars")
            total_tables = sum(len(p.tables) for p in pdf.pages)
            total_images = sum(len(p.images) for p in pdf.pages)
            print(f"    Tables: {total_tables}, Embedded images: {total_images}")

    if ingestion.errors:
        print("\nERRORS:")
        for err in ingestion.errors:
            print(f"  {err['file']}: {err['error']}")

    # Save results
    if args.output:
        output_path = Path(args.output)
    else:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = _PROJECT_ROOT / "evaluations" / "multimodal" / f"ingest_{timestamp}.json"

    save_results(ingestion, output_path)
    print(f"\nFull results saved to: {output_path}")


if __name__ == "__main__":
    main()