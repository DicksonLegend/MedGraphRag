"""
TXT/Markdown parser — plain text, whitespace normalization only
Memory-safe: caps file reads at MAX_TEXT_BODY_CHARS for large files.
"""

from pathlib import Path

from config import LARGE_FILE_THRESHOLD_BYTES, MAX_TEXT_BODY_CHARS


def parse_txt(filepath: Path) -> dict:
    """Parse a text or markdown file. Memory-safe — truncates files > 100 MB."""
    try:
        file_size = filepath.stat().st_size
        is_large = file_size > LARGE_FILE_THRESHOLD_BYTES
        max_chars = min(MAX_TEXT_BODY_CHARS, file_size) if is_large else file_size

        # Try utf-8 first, then common fallbacks
        encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
        content = None
        used_encoding = "utf-8"

        # For large files, read only what we need
        read_size = max_chars if max_chars > 0 else -1

        if is_large:
            # Large file path: read up to MAX_TEXT_BODY_CHARS chars
            for enc in encodings:
                try:
                    with open(filepath, "r", encoding=enc) as f:
                        content = f.read(max_chars)
                    used_encoding = enc
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue
        else:
            # Normal file: full read
            for enc in encodings:
                try:
                    with open(filepath, "r", encoding=enc) as f:
                        content = f.read()
                    used_encoding = enc
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue

        if content is None:
            read_mode = "r"
            read_bytes = read_size if read_size > 0 else None
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(read_bytes) if read_bytes else f.read()

        # Try to extract a title from first non-empty line
        title = None
        # Only scan first 10KB for title (avoid splitting huge string)
        head = content[:10240]
        for line in head.split("\n"):
            stripped = line.strip()
            if stripped:
                if stripped.startswith("#"):
                    title = stripped.lstrip("#").strip()
                else:
                    title = stripped[:200]
                break

        warnings = []
        if is_large or len(content) >= MAX_TEXT_BODY_CHARS:
            warnings.append(
                f"File truncated: {file_size} bytes → {len(content)} chars stored "
                f"(limit: {MAX_TEXT_BODY_CHARS})"
            )

        return {
            "text_body": content,
            "text_title": title,
            "text_abstract": None,
            "page_count": None,
            "structured_data": [],
            "figures": [],
            "metadata": {"extraction_tool": "text", "ocr_used": False},
            "source_metadata": {
                "encoding": used_encoding,
                "original_size_bytes": file_size,
                "truncated": len(content) < file_size,
            },
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
            "metadata": {"extraction_tool": "text", "ocr_used": False},
            "source_metadata": {},
            "extraction_warnings": [f"TXT parse error: {e}"],
        }
