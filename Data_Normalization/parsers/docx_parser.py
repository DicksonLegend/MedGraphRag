"""
DOCX parser — IBM Docling (GPU-accelerated)
"""

from pathlib import Path
from parsers._docling_common import docling_to_dict


def parse_docx(filepath: Path) -> dict:
    """Parse a DOCX file using Docling."""
    return docling_to_dict(filepath)
