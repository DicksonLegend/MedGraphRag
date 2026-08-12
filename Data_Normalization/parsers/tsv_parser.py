"""
TSV parser — Pandas (delimiter='\t')
Memory-safe: caps rows at MAX_STRUCTURED_DATA_ROWS for large files.
"""

from pathlib import Path
import pandas as pd

from config import MAX_STRUCTURED_DATA_ROWS, MAX_CSV_PREVIEW_ROWS


def parse_tsv(filepath: Path) -> dict:
    """Parse a TSV file. Memory-safe — caps rows for large files."""
    try:
        file_size = filepath.stat().st_size

        read_rows = MAX_STRUCTURED_DATA_ROWS
        df = pd.read_csv(filepath, delimiter="\t", encoding="utf-8",
                         low_memory=False, nrows=read_rows)

        total_rows = len(df)
        truncated = False
        # Peek for more rows
        try:
            next_chunk = pd.read_csv(filepath, delimiter="\t", encoding="utf-8",
                                     skiprows=range(1, total_rows + 1), nrows=1)
            truncated = len(next_chunk) > 0
        except Exception:
            pass

        # Build body
        body_rows = min(total_rows, MAX_CSV_PREVIEW_ROWS)
        body = df.head(body_rows).to_string()

        records = df.to_dict(orient="records")

        warnings = []
        if truncated:
            warnings.append(f"Rows truncated: more rows exist beyond {MAX_STRUCTURED_DATA_ROWS} stored")

        return {
            "text_body": body,
            "text_title": None,
            "text_abstract": None,
            "page_count": None,
            "structured_data": [{
                "headers": df.columns.tolist(),
                "rows": [list(r.values()) for r in records],
            }],
            "figures": [],
            "metadata": {"extraction_tool": "pandas", "ocr_used": False},
            "source_metadata": {
                "total_rows": total_rows + (1 if truncated else 0),
                "rows_stored": total_rows,
                "truncated": truncated,
                "original_size_bytes": file_size,
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
            "metadata": {"extraction_tool": "pandas", "ocr_used": False},
            "source_metadata": {},
            "extraction_warnings": [f"TSV parse error: {e}"],
        }
