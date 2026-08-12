"""
Common PDF/DOCX/PPTX parser — Hybrid strategy for speed

PDFs:        PyMuPDF fast-path first (text PDFs < 1s each)
             → Docling GPU only when PyMuPDF returns < 500 chars (scanned/image PDFs)
DOCX/PPTX:   Docling only (no fast fallback)
Images:      Docling OCR only
"""

import logging
import os
import re
import signal
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, TimeoutError

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Force CUDA for all torch operations
# ──────────────────────────────────────────────
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

# ──────────────────────────────────────────────
# Try Docling import (GPU, RTX 3050 6GB)
# ──────────────────────────────────────────────
_docling_available = False
_converter = None

try:
    import docling  # noqa: F401
    from docling.document_converter import DocumentConverter

    # Default converter auto-detects GPU (CUDA) and handles all format options
    _converter = DocumentConverter()
    _docling_available = True
    logger.info("Docling loaded with GPU support (RTX 3050 6GB)")
except ImportError:
    logger.info("Docling not available — using PyMuPDF for all PDFs")
except Exception as e:
    logger.warning(f"Docling init failed: {e} — using PyMuPDF for all PDFs")


# ──────────────────────────────────────────────
# Metadata extraction helpers (fixes #2-5)
# ──────────────────────────────────────────────

# Common date patterns
_DATE_PATTERNS = [
    re.compile(r"(?:Published|Date|Published online|Epub|Released)[\s:]+(\w+\s+\d{1,2},?\s+\d{4})", re.I),
    re.compile(r"(?:Published|Date)[\s:]+(\d{4}[-/]\d{2}[-/]\d{2})", re.I),
    re.compile(r"(?:Last updated|Updated)[\s:]+(\w+\s+\d{1,2},?\s+\d{4})", re.I),
    re.compile(r"(?:Last updated|Updated)[\s:]+(\d{4}[-/]\d{2}[-/]\d{2})", re.I),
    re.compile(r"©\s*(\d{4})", re.I),
    re.compile(r"Copyright\s+(?:©\s*)?(\d{4})", re.I),
]

_URL_PATTERN = re.compile(r"https?://[^\s<>\"'\)\],;]+", re.I)


def _clean_pdf_date(raw: str) -> str | None:
    """
    Clean PyMuPDF's raw date format (e.g. 'D:20241016000000Z') into 'YYYY-MM-DD'.
    Also handles ISO dates and common patterns.
    """
    if not raw:
        return None
    raw = raw.strip()
    # PyMuPDF format: D:YYYYMMDDHHMMSS...
    m = re.match(r"D:(\d{4})(\d{2})(\d{2})", raw)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # Already ISO: YYYY-MM-DD
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return raw
    return raw

_AUTHOR_PATTERNS = [
    re.compile(r"(?:Author|Authors?|Written by|Prepared by|By)[\s:]+(.+?)(?:\n|$)", re.I),
    re.compile(r"©\s*\d{4}\s+(.+?)(?:\n|$)", re.I),
    re.compile(r"Copyright\s+(?:©\s*)?\d{4}\s+(.+?)(?:\n|$)", re.I),
]


def _extract_author_from_text(body: str) -> str | None:
    """Regex fallback: extract author/organization from body text."""
    if not body:
        return None
    head = body[:2000]
    for pattern in _AUTHOR_PATTERNS:
        m = pattern.search(head)
        if m:
            author = m.group(1).strip()
            # Clean trailing punctuation
            author = author.rstrip(".,;:)")
            if len(author) > 3 and len(author) < 200:
                return author
    return None


def _extract_metadata_from_pdf_doc(doc) -> dict:
    """Extract title, author, date, url from PyMuPDF document metadata."""
    meta = {}
    try:
        info = doc.metadata or {}
        meta["title"] = info.get("title") or info.get("Subject") or None
        meta["author"] = info.get("author") or info.get("Creator") or info.get("Producer") or None
        raw_date = info.get("creationDate") or info.get("modDate") or None
        meta["publication_date"] = _clean_pdf_date(raw_date)
        meta["url"] = info.get("url") or info.get("URL") or None
        # Clean up empty strings
        for k, v in meta.items():
            if v and not v.strip():
                meta[k] = None
    except Exception:
        pass
    return meta


def _extract_title_from_text(body: str) -> str | None:
    """Regex fallback: extract title from first non-empty heading-like line."""
    if not body:
        return None
    for line in body.split("\n")[:30]:
        stripped = line.strip()
        if not stripped:
            continue
        # Skip common non-title lines
        low = stripped.lower()
        if low.startswith(("published", "copyright", "doi:", "http", "volume", "issue")):
            continue
        if len(stripped) > 10 and len(stripped) < 300:
            return stripped
    return None


def _extract_date_from_text(body: str) -> str | None:
    """Regex fallback: extract publication date from body text."""
    if not body:
        return None
    # Search first 2000 chars (header area)
    head = body[:2000]
    for pattern in _DATE_PATTERNS:
        m = pattern.search(head)
        if m:
            return m.group(1).strip()
    return None


def _extract_url_from_text(body: str) -> str | None:
    """Regex fallback: extract a URL from body text, handling line-breaks."""
    if not body:
        return None
    head = body[:3000]
    # Remove newlines that break URLs (PDF line-break hyph enation)
    # e.g. "https://www.nice.org.uk/terms-and-\nconditions" -> "https://www.nice.org.uk/terms-and-\nconditions"
    cleaned = re.sub(r"-\n\s*", "-", head)  # "terms-and-\nconditions" -> "terms-and-conditions"
    m = _URL_PATTERN.search(cleaned)
    return m.group(0) if m else None


# ──────────────────────────────────────────────
# PyMuPDF fast path
# ──────────────────────────────────────────────
def _extract_pymupdf(filepath: Path) -> dict:
    """Fast text extraction from text-based PDFs using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(filepath))
        pages_text = []
        body_parts = []
        for page in doc:
            text = page.get_text()
            if text.strip():
                pages_text.append(text)
                body_parts.append(text)
        body = "\n\n".join(body_parts)
        page_count = len(doc)
        char_count = len(body) if body else 0

        # Extract metadata from PDF document info
        pdf_meta = _extract_metadata_from_pdf_doc(doc)
        doc.close()

        # Build title: PDF metadata first, then regex fallback
        title = pdf_meta.get("title")
        if not title:
            title = _extract_title_from_text(body)

        # Build other metadata: PDF metadata first, then regex fallback
        author = pdf_meta.get("author")
        pub_date = pdf_meta.get("publication_date")
        if not pub_date:
            pub_date = _extract_date_from_text(body)
        url = pdf_meta.get("url")
        if not url:
            url = _extract_url_from_text(body)

        warnings = [] if char_count > 0 else ["PyMuPDF extracted zero characters"]

        return {
            "text_body": body,
            "text_title": title,
            "text_abstract": None,
            "page_count": page_count,
            "structured_data": [],
            "figures": [],
            "metadata": {"extraction_tool": "PyMuPDF", "ocr_used": False},
            "source_metadata": {
                "pymupdf_char_count": char_count,
                "author": author,
                "publication_date": pub_date,
                "url": url,
            },
            "extraction_warnings": warnings,
        }
    except ImportError:
        return {
            "text_body": None,
            "text_title": None,
            "text_abstract": None,
            "page_count": None,
            "structured_data": [],
            "figures": [],
            "metadata": {"extraction_tool": None, "ocr_used": False},
            "source_metadata": {},
            "extraction_warnings": ["PyMuPDF not installed"],
        }


# ──────────────────────────────────────────────
# Docling GPU path
# ──────────────────────────────────────────────
DOCLING_TIMEOUT_S = 10  # Max seconds per PDF before falling back

# Set to True to skip Docling OCR entirely (fast pass, process all files quickly)
SKIP_DOCLING = True

def _extract_docling(filepath: Path) -> dict:
    """Full pipeline extraction using Docling (GPU), with timeout."""
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_converter.convert, str(filepath))
            result = future.result(timeout=DOCLING_TIMEOUT_S)
        doc = result.document

        # Body text
        body_parts = []
        if hasattr(doc, "iterate_items"):
            for item in doc.iterate_items():
                if hasattr(item, "type") and item.type == "text":
                    body_parts.append(item.text if hasattr(item, "text") else "")
        body = "\n\n".join(body_parts) if body_parts else (doc.export_to_text() if hasattr(doc, "export_to_text") else "")

        # Title — Docling heading first, then regex fallback from body
        title = None
        if hasattr(doc, "headings") and doc.headings:
            h = doc.headings[0]
            title = h.text if hasattr(h, "text") else (str(h) if h else None)
        if not title:
            title = _extract_title_from_text(body)

        # Author, date, url — regex extraction from body
        author = _extract_author_from_text(body)
        pub_date = _extract_date_from_text(body)
        url = _extract_url_from_text(body)

        # Tables
        tables = []
        if hasattr(doc, "tables") and doc.tables:
            for table in doc.tables:
                if hasattr(table, "export_to_dataframe"):
                    df = table.export_to_dataframe()
                    if df is not None:
                        tables.append({
                            "headers": df.columns.tolist(),
                            "rows": df.values.tolist(),
                        })

        # Figures
        figures = []
        if hasattr(doc, "figures") and doc.figures:
            for fig in doc.figures:
                cap = fig.caption.text if hasattr(fig, "caption") and fig.caption else None
                figures.append({
                    "type": "figure",
                    "label": fig.label if hasattr(fig, "label") else None,
                    "caption": cap,
                })

        page_count = len(result.pages) if hasattr(result, "pages") else None

        return {
            "text_body": body,
            "text_title": title,
            "text_abstract": None,
            "page_count": page_count,
            "structured_data": tables,
            "figures": figures,
            "metadata": {"extraction_tool": "Docling", "ocr_used": False},
            "source_metadata": {
                "author": author,
                "publication_date": pub_date,
                "url": url,
            },
            "extraction_warnings": [],
        }
    except Exception as e:
        logger.warning(f"Docling failed for {filepath.name}: {e}")
        return {
            "text_body": None,
            "text_title": None,
            "text_abstract": None,
            "page_count": None,
            "structured_data": [],
            "figures": [],
            "metadata": {"extraction_tool": "Docling", "ocr_used": False},
            "source_metadata": {},
            "extraction_warnings": [f"Docling error: {e}"],
        }


# ──────────────────────────────────────────────
# Main dispatch
# ──────────────────────────────────────────────
def docling_to_dict(filepath: Path) -> dict:
    """
    Parse a document to a standardized dict.

    PDFs:     PyMuPDF fast-path → if < 500 chars → Docling GPU OCR (scanned PDF)
    DOCX/PPTX: Docling only (no fast fallback available)
    Images:   Docling OCR only
    """
    ext = filepath.suffix.lower()

    # ── Non-PDF formats: Docling only ──
    if ext not in (".pdf",):
        if not _docling_available:
            return {
                "text_body": None, "text_title": None, "text_abstract": None,
                "page_count": None, "structured_data": [], "figures": [],
                "metadata": {"extraction_tool": None, "ocr_used": False},
                "source_metadata": {},
                "extraction_warnings": [f"No parser available for {ext} — Docling not loaded"],
            }
        return _extract_docling(filepath)

    # ── PDF: fast path first ──
    try:
        import fitz
        pymupdf_ok = True
    except ImportError:
        pymupdf_ok = False

    if pymupdf_ok:
        result = _extract_pymupdf(filepath)
        char_count = result.get("source_metadata", {}).get("pymupdf_char_count", 0)

        # If PyMuPDF got meaningful text, return immediately (fast path)
        if char_count >= 1000:
            return result

        # PyMuPDF got little/no text → likely a scanned PDF → try Docling GPU
        # SKIP_DOCLING: skip OCR entirely for fast processing pass
        if _docling_available and not SKIP_DOCLING:
            logger.info(f"PyMuPDF sparse ({char_count}c) — trying Docling OCR on {filepath.name}")
            docling_result = _extract_docling(filepath)
            if docling_result.get("text_body") and len(docling_result["text_body"]) > char_count:
                docling_result["extraction_warnings"].append(
                    f"Fallback Docling: PyMuPDF returned only {char_count} chars (scanned PDF)"
                )
                return docling_result
            # Docling didn't improve — keep PyMuPDF result
            result["extraction_warnings"].append(f"Docling fallback produced no improvement; keeping PyMuPDF ({char_count}c)")
            return result

        # No Docling available — return PyMuPDF result as-is
        if char_count == 0:
            result["extraction_warnings"].append("PyMuPDF extracted 0 characters — PDF may be scanned with no OCR available")
        return result

    # ── PyMuPDF not installed — try Docling ──
    if _docling_available:
        return _extract_docling(filepath)

    return {
        "text_body": None, "text_title": None, "text_abstract": None,
        "page_count": None, "structured_data": [], "figures": [],
        "metadata": {"extraction_tool": None, "ocr_used": False},
        "source_metadata": {},
        "extraction_warnings": ["No PDF extraction tool available"],
    }
