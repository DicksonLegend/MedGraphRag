"""
Archive parser — extracts ZIP archives and dispatches to recursive file processing.
"""

from pathlib import Path
import zipfile

from config import ARCHIVE_EXTENSIONS


def parse_archive(filepath: Path) -> dict:
    """
    Parse a ZIP archive by extracting and listing contents.
    Individual files are processed by the main pipeline recursively.
    This just returns the index/manifest of the archive.
    """
    try:
        extracted_files = []
        extraction_dir = None

        if filepath.suffix.lower() == ".zip":
            with zipfile.ZipFile(filepath, "r") as zf:
                for info in zf.infolist():
                    if not info.is_dir():
                        extracted_files.append(info.filename)

        return {
            "text_body": None,
            "text_title": filepath.stem,
            "text_abstract": None,
            "page_count": None,
            "structured_data": [],
            "figures": [],
            "metadata": {"extraction_tool": "zipfile", "ocr_used": False},
            "source_metadata": {
                "archive_type": "zip",
                "num_files_in_archive": len(extracted_files),
                "file_list": extracted_files,
            },
            "extraction_warnings": [],
        }
    except Exception as e:
        return {
            "text_body": None,
            "text_title": None,
            "text_abstract": None,
            "page_count": None,
            "structured_data": [],
            "figures": [],
            "metadata": {"extraction_tool": "zipfile", "ocr_used": False},
            "source_metadata": {},
            "extraction_warnings": [f"Archive parse error: {e}"],
        }
