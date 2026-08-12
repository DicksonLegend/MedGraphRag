"""
Parquet parser — Pandas (pyarrow engine)
Memory-safe: caps rows at MAX_STRUCTURED_DATA_ROWS for large files.
Converts numpy types to Python native types for JSON serialization.
"""

import json
from pathlib import Path
import pandas as pd

from config import MAX_STRUCTURED_DATA_ROWS, MAX_CSV_PREVIEW_ROWS


def _to_native(v):
    """Convert numpy types to Python native types for JSON serialization."""
    import numpy as np
    if isinstance(v, (np.integer,)):
        return int(v)
    elif isinstance(v, (np.floating,)):
        return float(v)
    elif isinstance(v, (np.ndarray,)):
        return [_to_native(x) for x in v.tolist()]
    elif isinstance(v, (np.bool_,)):
        return bool(v)
    elif isinstance(v, dict):
        return {k: _to_native(val) for k, val in v.items()}
    elif isinstance(v, (list, tuple)):
        return [_to_native(x) for x in v]
    return v


def parse_parquet(filepath: Path) -> dict:
    """Parse a Parquet file. Memory-safe — caps rows for large files."""
    try:
        file_size = filepath.stat().st_size

        read_rows = MAX_STRUCTURED_DATA_ROWS
        df = pd.read_parquet(filepath, engine="pyarrow")

        total_rows = len(df)
        truncated = False

        if total_rows > read_rows:
            df = df.head(read_rows)
            truncated = True

        # Build body from first MAX_CSV_PREVIEW_ROWS rows
        body_rows = min(len(df), MAX_CSV_PREVIEW_ROWS)
        body = df.head(body_rows).to_string()

        records = df.to_dict(orient="records")

        # Convert to JSON-safe native types
        rows_safe = []
        for r in records:
            rows_safe.append([_to_native(v) for v in r.values()])

        warnings = []
        if truncated:
            warnings.append(
                f"Rows truncated: {total_rows} total → {len(df)} rows stored "
                f"(limit: {MAX_STRUCTURED_DATA_ROWS})"
            )

        return {
            "text_body": body,
            "text_title": None,
            "text_abstract": None,
            "page_count": None,
            "structured_data": [{
                "headers": df.columns.tolist(),
                "rows": rows_safe,
            }],
            "figures": [],
            "metadata": {"extraction_tool": "pandas+pyarrow", "ocr_used": False},
            "source_metadata": {
                "total_rows": total_rows,
                "rows_stored": len(df),
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
            "metadata": {"extraction_tool": "pandas+pyarrow", "ocr_used": False},
            "source_metadata": {},
            "extraction_warnings": [f"Parquet parse error: {e}"],
        }
