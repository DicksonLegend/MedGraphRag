"""
Image parser — IBM Docling (GPU-accelerated via Docling OCR)
Converts images to text using Docling's OCR pipeline.
"""

from pathlib import Path
from parsers._docling_common import docling_to_dict


def parse_image(filepath: Path) -> dict:
    """Parse an image file (PNG, JPG, TIFF, BMP) using Docling OCR."""
    return docling_to_dict(filepath)
