"""
MedGraphRAG Backend — Upload Security & Magic-Byte Validation (F-06)
====================================================================
Sniffs binary magic bytes on incoming multipart file uploads to prevent
MIME-type spoofing, polyglot files, and parser exploits.
Enforces PyMuPDF page caps (<=200 pages) and rejects encrypted PDFs.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Tuple

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

# Magic byte signatures
MAGIC_PDF = b"%PDF"
MAGIC_PNG = b"\x89PNG\r\n\x1a\n"
MAGIC_JPEG = b"\xff\xd8\xff"
MAGIC_ZIP_XLSX = b"PK\x03\x04"
MAGIC_DICOM_PREFIX = b"DICM"  # At byte offset 128 in standard DICOM


def validate_file_magic_bytes(file_bytes: bytes, filename: str) -> str:
    """
    Verify that file content magic bytes match the claimed file extension.
    Returns detected canonical format: 'pdf', 'png', 'jpeg', 'dicom', 'xlsx', 'csv'.
    Raises HTTPException(415) on mismatch or invalid signature.
    """
    ext = Path(filename).suffix.lower()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes).",
        )

    # 1. PDF
    if ext == ".pdf":
        if not file_bytes.startswith(MAGIC_PDF):
            logger.warning("Magic mismatch: claimed .pdf but file does not start with %%PDF- (file=%s)", filename)
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="File content does not match PDF format (%PDF header missing).",
            )
        return "pdf"

    # 2. PNG
    if ext == ".png":
        if not file_bytes.startswith(b"\x89PNG"):
            logger.warning("Magic mismatch: claimed .png but magic bytes missing (file=%s)", filename)
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="File content does not match PNG format (PNG header missing).",
            )
        return "png"

    # 3. JPEG / JPG
    if ext in (".jpg", ".jpeg"):
        if not file_bytes.startswith(b"\xff\xd8"):
            logger.warning("Magic mismatch: claimed JPEG but magic bytes missing (file=%s)", filename)
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="File content does not match JPEG format (JPEG SOI marker missing).",
            )
        return "jpeg"

    # 4. DICOM (.dcm)
    if ext in (".dcm", ".dicom"):
        # Standard DICOM has 128-byte preamble followed by 'DICM'
        is_dicom = False
        if len(file_bytes) > 132 and file_bytes[128:132] == MAGIC_DICOM_PREFIX:
            is_dicom = True
        elif file_bytes.startswith(b"\x08\x00") or file_bytes.startswith(b"\xd8\xff"):
            # Headerless/raw DICOM stream
            is_dicom = True

        if not is_dicom:
            logger.warning("Magic mismatch: claimed DICOM but header missing (file=%s)", filename)
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="File content does not match valid DICOM format (DICM marker missing).",
            )
        return "dicom"

    # 5. XLSX (Office Open XML ZIP container)
    if ext == ".xlsx":
        if not file_bytes.startswith(MAGIC_ZIP_XLSX):
            logger.warning("Magic mismatch: claimed .xlsx but PK zip header missing (file=%s)", filename)
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="File content does not match XLSX spreadsheet format (PK header missing).",
            )
        return "xlsx"

    # 6. CSV (Plain text tabular)
    if ext == ".csv":
        try:
            # Check UTF-8 / ASCII decodability of head
            sample = file_bytes[:4096].decode("utf-8")
            if "\x00" in sample:  # Binary NUL byte detected in supposed CSV
                raise ValueError("Binary NUL bytes found in CSV")
        except Exception:
            logger.warning("Magic mismatch: claimed .csv but contains non-text binary data (file=%s)", filename)
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="File content does not match plain text CSV format.",
            )
        return "csv"

    # 7. Other images (TIFF, BMP)
    if ext in (".tif", ".tiff"):
        if not (file_bytes.startswith(b"II*\x00") or file_bytes.startswith(b"MM\x00*")):
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Invalid TIFF header.")
        return "tiff"
    if ext == ".bmp":
        if not file_bytes.startswith(b"BM"):
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Invalid BMP header.")
        return "bmp"

    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail=f"Unsupported file extension '{ext}'.",
    )


def validate_pdf_safety_caps(doc_or_bytes, max_pages: int = 200) -> None:
    """
    Validate PDF page count (<= 200) and reject encrypted / password-protected PDFs.
    """
    try:
        import fitz
        if isinstance(doc_or_bytes, bytes):
            doc = fitz.open(stream=doc_or_bytes, filetype="pdf")
        else:
            doc = doc_or_bytes

        if doc.is_encrypted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password-protected or encrypted PDFs are not supported.",
            )

        if doc.page_count > max_pages:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"PDF document exceeds maximum allowed page count ({doc.page_count} > {max_pages} pages).",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.debug("PDF safety validation warning: %s", e)
