"""
MedGraphRAG Backend — Stage A: Multi-Format Report Parser
==========================================================
Supports PDF, Image (JPG/PNG), XLSX, and CSV diagnostic lab reports.
Strictly uses PyMuPDF (fitz) + pdfplumber for PDF tables (no Docling).
Parses images via EasyOCR / pytesseract / OCR fallback with confidence tracking.
Parses spreadsheets via pandas + openpyxl preserving exact cell strings and numbers.
"""

from __future__ import annotations

import hashlib
import io
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

import fitz  # PyMuPDF
import pdfplumber
import pandas as pd
from PIL import Image

from app.core.report.schemas import ParsedReport

logger = logging.getLogger(__name__)

# OCR Confidence threshold for flagging needs_review
OCR_CONFIDENCE_THRESHOLD = 0.75


def parse_report_bytes(file_bytes: bytes, filename: str) -> ParsedReport:
    """
    Main entry point for multi-format report parsing.

    Parameters
    ----------
    file_bytes : bytes
        Raw binary contents of the uploaded report.
    filename : str
        Original filename to infer format extension.

    Returns
    -------
    ParsedReport
    """
    raw_hash = hashlib.sha256(file_bytes).hexdigest()
    ext = Path(filename).suffix.lower()

    logger.info("Parsing report %s (ext=%s, size=%d bytes, sha256=%s)", filename, ext, len(file_bytes), raw_hash[:8])

    if ext == ".pdf":
        return _parse_pdf(file_bytes, raw_hash)
    elif ext in (".png", ".jpg", ".jpeg", ".bmp", ".tiff"):
        return _parse_image(file_bytes, raw_hash)
    elif ext in (".xlsx", ".xls"):
        return _parse_excel(file_bytes, raw_hash)
    elif ext == ".csv":
        return _parse_csv(file_bytes, raw_hash)
    else:
        # Fallback text parse attempt
        try:
            text = file_bytes.decode("utf-8", errors="replace")
            return ParsedReport(
                raw_text=text,
                text_blocks=[text],
                tables=[],
                format=ext.lstrip(".") or "txt",
                raw_bytes_hash=raw_hash,
                needs_review=False,
            )
        except Exception as e:
            logger.error("Failed to parse unknown file format %s: %s", filename, e)
            raise ValueError(f"Unsupported or corrupt file format: {ext}")


def _parse_pdf(file_bytes: bytes, raw_hash: str) -> ParsedReport:
    """Parse PDF using PyMuPDF fitz for text/fitz.find_tables() + pdfplumber for tables."""
    text_blocks: List[str] = []
    tables: List[List[List[str]]] = []
    needs_review = False

    # Pass 1: PyMuPDF for clean text extraction and find_tables()
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for page_num, page in enumerate(doc, start=1):
            page_text = page.get_text("text")
            if page_text.strip():
                text_blocks.append(page_text)

            # PyMuPDF table extraction
            try:
                tabs = page.find_tables()
                if tabs and tabs.tables:
                    for t in tabs.tables:
                        table_data = t.extract()
                        # Clean nulls to empty strings
                        cleaned_table = [
                            [str(cell or "").strip() for cell in row]
                            for row in table_data
                        ]
                        if cleaned_table:
                            tables.append(cleaned_table)
            except Exception as te:
                logger.debug("PyMuPDF find_tables page %d warning: %s", page_num, te)

    # Pass 2: Fallback to pdfplumber if tables empty or PyMuPDF extracted low text
    if not tables:
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    plumb_tables = page.extract_tables()
                    for pt in plumb_tables:
                        cleaned_table = [
                            [str(cell or "").strip() for cell in row]
                            for row in pt
                        ]
                        if cleaned_table:
                            tables.append(cleaned_table)
        except Exception as pe:
            logger.warning("pdfplumber table extraction warning: %s", pe)

    full_text = "\n\n".join(text_blocks)
    if not full_text.strip() and not tables:
        needs_review = True
        full_text = "[WARNING: PDF yielded no readable text or tables]"

    return ParsedReport(
        raw_text=full_text,
        text_blocks=text_blocks,
        tables=tables,
        format="pdf",
        raw_bytes_hash=raw_hash,
        needs_review=needs_review,
    )


def _parse_image(file_bytes: bytes, raw_hash: str) -> ParsedReport:
    """Parse image via EasyOCR / pytesseract with confidence tracking."""
    text_blocks: List[str] = []
    tables: List[List[List[str]]] = []
    images_meta: List[Dict[str, Any]] = []
    needs_review = False
    avg_confidence = 1.0

    try:
        image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    except Exception as e:
        logger.error("Failed to open image bytes: %s", e)

    # Attempt EasyOCR first if installed
    easyocr_success = False
    try:
        import easyocr
        import numpy as np

        reader = easyocr.Reader(["en"], gpu=False)
        img_np = np.array(image)
        ocr_results = reader.readtext(img_np)

        confidences = []
        lines = []
        for bbox, text, prob in ocr_results:
            lines.append(text)
            confidences.append(float(prob))

        if confidences:
            avg_confidence = sum(confidences) / len(confidences)
            if avg_confidence < OCR_CONFIDENCE_THRESHOLD:
                needs_review = True

        full_text = "\n".join(lines)
        text_blocks.append(full_text)
        images_meta.append({"ocr_engine": "easyocr", "avg_confidence": avg_confidence, "lines_count": len(lines)})
        easyocr_success = True
    except Exception as e:
        logger.warning("EasyOCR failed or not installed, attempting pytesseract/PIL fallback: %s", e)

    # Fallback to pytesseract if EasyOCR failed
    if not easyocr_success:
        try:
            import pytesseract

            full_text = pytesseract.image_to_string(image)
            text_blocks.append(full_text)
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            confs = [float(c) for c in data.get("conf", []) if float(c) > 0]
            if confs:
                avg_confidence = (sum(confs) / len(confs)) / 100.0
                if avg_confidence < OCR_CONFIDENCE_THRESHOLD:
                    needs_review = True
            images_meta.append({"ocr_engine": "pytesseract", "avg_confidence": avg_confidence})
        except Exception as pe:
            logger.warning("Pytesseract fallback failed: %s", pe)
            full_text = "[OCR UNAVAILABLE: Please verify lab image contents manually]"
            text_blocks.append(full_text)
            needs_review = True
            images_meta.append({"ocr_engine": "none", "avg_confidence": 0.0})

    return ParsedReport(
        raw_text="\n".join(text_blocks),
        text_blocks=text_blocks,
        tables=tables,
        format="image",
        raw_bytes_hash=raw_hash,
        images_meta=images_meta,
        needs_review=needs_review,
    )


def _parse_excel(file_bytes: bytes, raw_hash: str) -> ParsedReport:
    """Parse XLSX / XLS using pandas + openpyxl, preserving every cell exactly."""
    text_blocks: List[str] = []
    tables: List[List[List[str]]] = []

    try:
        excel_file = pd.ExcelFile(io.BytesIO(file_bytes), engine="openpyxl")
        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet_name, dtype=str)
            # Replace NaNs with empty string
            df = df.fillna("")
            table_rows = [df.columns.tolist()] + df.values.tolist()
            # Clean string conversions
            table_rows = [[str(cell).strip() for cell in row] for row in table_rows]
            tables.append(table_rows)

            # Build text representation
            sheet_text = f"--- Sheet: {sheet_name} ---\n" + "\n".join(["\t".join(row) for row in table_rows])
            text_blocks.append(sheet_text)
    except Exception as e:
        logger.error("Failed to parse Excel spreadsheet: %s", e)
        raise ValueError(f"Failed to parse Excel spreadsheet: {e}")

    full_text = "\n\n".join(text_blocks)
    return ParsedReport(
        raw_text=full_text,
        text_blocks=text_blocks,
        tables=tables,
        format="xlsx",
        raw_bytes_hash=raw_hash,
        needs_review=False,
    )


def _parse_csv(file_bytes: bytes, raw_hash: str) -> ParsedReport:
    """Parse CSV using pandas, preserving exact cell strings."""
    try:
        df = pd.read_csv(io.BytesIO(file_bytes), dtype=str)
        df = df.fillna("")
        table_rows = [df.columns.tolist()] + df.values.tolist()
        table_rows = [[str(cell).strip() for cell in row] for row in table_rows]

        sheet_text = "\n".join(["\t".join(row) for row in table_rows])
        return ParsedReport(
            raw_text=sheet_text,
            text_blocks=[sheet_text],
            tables=[table_rows],
            format="csv",
            raw_bytes_hash=raw_hash,
            needs_review=False,
        )
    except Exception as e:
        logger.error("Failed to parse CSV file: %s", e)
        raise ValueError(f"Failed to parse CSV file: {e}")
