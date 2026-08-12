"""
PDF parser — IBM Docling (GPU, RTX 3050 6GB)
Converts PDF to text with Docling pipeline; falls back to PyMuPDF if Docling fails.
"""

from pathlib import Path
from parsers._docling_common import docling_to_dict


def parse_pdf(filepath: Path) -> dict:
    """
    Parse a PDF file using Docling (GPU-accelerated).
    Falls back to PyMuPDF if Docling fails for any reason.
    Returns: {
        "text_body": str,
        "text_title": str | None,
        "text_abstract": str | None,
        "page_count": int,
        "structured_data": list,
        "figures": list,
        "metadata": dict,
        "source_metadata": dict,
        "extraction_warnings": list,
    }
    """
    return docling_to_dict(filepath)
