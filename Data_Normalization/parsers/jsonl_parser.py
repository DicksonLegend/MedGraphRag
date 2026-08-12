"""
JSONL parser — line-delimited JSON
Memory-safe: caps lines at MAX_JSONL_LINES for large files.
One JSON per line; arrays of dicts go into structured_data.
"""

from pathlib import Path
import json

from config import MAX_JSONL_LINES, MAX_TEXT_BODY_CHARS


def parse_jsonl(filepath: Path) -> dict:
    """Parse a JSONL file. Memory-safe — caps at MAX_JSONL_LINES lines."""
    try:
        lines = []
        total_lines = 0
        truncated = False
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    total_lines += 1
                    continue
                total_lines += 1
                if len(lines) < MAX_JSONL_LINES:
                    lines.append(json.loads(line))
                elif not truncated:
                    truncated = True

        # Build body from first items
        body_parts = [json.dumps(item, indent=2, ensure_ascii=False) for item in lines]
        body = "\n".join(body_parts)

        # Cap body length
        warnings = []
        if truncated:
            warnings.append(
                f"Lines truncated: {total_lines} total lines → "
                f"{len(lines)} stored (limit: {MAX_JSONL_LINES})"
            )
        if len(body) > MAX_TEXT_BODY_CHARS:
            body = body[:MAX_TEXT_BODY_CHARS]
            warnings.append(
                f"Body truncated: {len(body)} chars → {MAX_TEXT_BODY_CHARS} chars"
            )

        return {
            "text_body": body,
            "text_title": None,
            "text_abstract": None,
            "page_count": None,
            "structured_data": lines if isinstance(lines, list) else [],
            "figures": [],
            "metadata": {"extraction_tool": "jsonl", "ocr_used": False},
            "source_metadata": {
                "num_lines": total_lines,
                "lines_stored": len(lines),
                "truncated": truncated,
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
            "metadata": {"extraction_tool": "jsonl", "ocr_used": False},
            "source_metadata": {},
            "extraction_warnings": [f"JSONL parse error: {e}"],
        }
