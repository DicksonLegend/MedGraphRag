"""
JSON parser — native json module
Memory-safe: caps text body for large files, avoids storing raw data in source_metadata.
"""

from pathlib import Path
import json

from config import LARGE_FILE_THRESHOLD_BYTES, MAX_TEXT_BODY_CHARS


def parse_json(filepath: Path) -> dict:
    """Parse a JSON file. Memory-safe — caps body for large files."""
    try:
        file_size = filepath.stat().st_size
        is_large = file_size > LARGE_FILE_THRESHOLD_BYTES

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Convert to text representation
        body = json.dumps(data, indent=2, ensure_ascii=False)

        # Try to find title and abstract if it looks like a paper
        title = None
        abstract = None
        if isinstance(data, dict):
            for key in ("title", "Title", "TITLE"):
                if key in data and isinstance(data[key], str):
                    title = data[key]
                    break
            for key in ("abstract", "Abstract", "ABSTRACT", "abstractText"):
                if key in data and isinstance(data[key], str):
                    abstract = data[key]
                    break

        warnings = []

        # Cap body for large files
        if is_large or len(body) > MAX_TEXT_BODY_CHARS:
            body = body[:MAX_TEXT_BODY_CHARS]
            warnings.append(
                f"Body truncated: original size {file_size} bytes → "
                f"{MAX_TEXT_BODY_CHARS} chars stored"
            )

        # Don't store full data in source_metadata for large files
        if is_large:
            source_metadata = {
                "_data_type": type(data).__name__,
                "truncated": True,
                "original_size_bytes": file_size,
            }
        else:
            source_metadata = data if isinstance(data, dict) else {"_data_type": type(data).__name__}

        return {
            "text_body": body,
            "text_title": title,
            "text_abstract": abstract,
            "page_count": None,
            "structured_data": [],
            "figures": [],
            "metadata": {"extraction_tool": "json", "ocr_used": False},
            "source_metadata": source_metadata,
            "extraction_warnings": warnings,
        }
    except Exception as e:
        return {
            "text_body": None,
            "text_title": None,
            "text_abstract": None,
            "page_count": None,
            "structured_data": [],
            "figures": [],
            "metadata": {"extraction_tool": "json", "ocr_used": False},
            "source_metadata": {},
            "extraction_warnings": [f"JSON parse error: {e}"],
        }
