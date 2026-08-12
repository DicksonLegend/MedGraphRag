"""
RRF parser — pipe-delimited (RxNorm format)
Memory-safe: caps rows at MAX_STRUCTURED_DATA_ROWS for large files.
"""

from pathlib import Path
import csv

from config import MAX_STRUCTURED_DATA_ROWS, MAX_CSV_PREVIEW_ROWS


def parse_rrf(filepath: Path) -> dict:
    """Parse an RRF file (pipe-delimited RxNorm format). Memory-safe."""
    try:
        rows = []
        total_rows = 0
        truncated = False
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="|")
            for row in reader:
                # Remove empty trailing column (typical in RRF)
                if row and row[-1] == "":
                    row = row[:-1]
                total_rows += 1
                if total_rows <= MAX_STRUCTURED_DATA_ROWS:
                    rows.append(row)
                else:
                    # Reached the cap — mark truncated and stop reading.
                    # Avoids scanning a multi-GB file to count every row.
                    truncated = True
                    break

        # Build body from first MAX_CSV_PREVIEW_ROWS rows only
        body_parts = []
        preview_count = min(len(rows), MAX_CSV_PREVIEW_ROWS)
        for i in range(preview_count):
            body_parts.append("|".join(rows[i]))
        body = "\n".join(body_parts)

        warnings = []
        if truncated or total_rows > MAX_STRUCTURED_DATA_ROWS:
            warnings.append(
                f"Rows truncated: {total_rows} total → {len(rows)} rows stored "
                f"(limit: {MAX_STRUCTURED_DATA_ROWS})"
            )

        return {
            "text_body": body,
            "text_title": filepath.stem,
            "text_abstract": None,
            "page_count": None,
            "structured_data": [{
                "headers": [],
                "rows": rows,
            }],
            "figures": [],
            "metadata": {"extraction_tool": "csv+pipe", "ocr_used": False},
            "source_metadata": {
                "total_rows": total_rows,
                "rows_stored": len(rows),
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
            "metadata": {"extraction_tool": "csv+pipe", "ocr_used": False},
            "source_metadata": {},
            "extraction_warnings": [f"RRF parse error: {e}"],
        }
