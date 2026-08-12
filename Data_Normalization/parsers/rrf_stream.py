"""
RRF streaming writer — writes the *full* pipe-delimited content row-by-row,
never holding all rows in memory. Used for large UMLS RRF files (MRREL, MRHIER,
MRCONSO, ...) that would OOM if loaded as a list.

Produces a JSON document structurally compatible with `build_output_schema`
v1.2, but streams the `structured_data[].rows` array directly to disk with an
explicit write loop (no giant in-memory list).
"""

import json
import csv
from pathlib import Path
from datetime import datetime, timezone

from config import SCHEMA_VERSION
from schema import detect_encoding
from utils import compute_sha256

# text.body preview cap (kept small regardless of file size)
MAX_BODY_PREVIEW_ROWS = 500


def _iter_rows(filepath: Path):
    """Yield normalized (pipe fields, trailing empty dropped) rows lazily."""
    with open(filepath, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f, delimiter="|")
        for row in reader:
            if row and row[-1] == "":
                row = row[:-1]
            yield row


def stream_rrf_to_json(
    filepath: Path,
    output_path: Path,
    datasets_dir: Path,
    folder_name: str,
    subcategory: str,
    format_ext: str,
    file_hash: str | None = None,
) -> dict:
    """Stream a pipe-delimited RRF file into normalized JSON, row-by-row.

    Returns a summary dict mirroring `process_file`'s success payload.
    """
    file_hash = file_hash or compute_sha256(filepath)
    st = filepath.stat()
    enc = detect_encoding(filepath)

    rel = filepath.relative_to(datasets_dir)
    parts = list(rel.parts)
    subpath = str(Path(*parts[1:-1])) if len(parts) > 2 else ""
    stem = filepath.stem
    doc_id = str(Path(folder_name) / subpath / stem) if subpath else str(Path(folder_name) / stem)

    tool = "csv+pipe"
    ocr_used = False

    # Pass 1: gather the small text.body preview + count rows (cheap).
    preview = []
    total_rows = 0
    for row in _iter_rows(filepath):
        total_rows += 1
        if len(preview) < MAX_BODY_PREVIEW_ROWS:
            preview.append("|".join(row))
    body_text = "\n".join(preview)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    fixed_head = {
        "schema_version": SCHEMA_VERSION,
        "document_id": doc_id,
        "source": folder_name,
        "subpath": subpath,
        "subcategory": subcategory,
        "dataset_version": None,
        "title": stem,
        "author": None,
        "language": None,
        "format": (format_ext or "rrf").lstrip("."),
        "category": subcategory,
        "text": {
            "title": stem,
            "abstract": None,
            "body": body_text,
        },
    }
    fixed_tail = {
        "figures": [],
        "page_count": None,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "original_path": str(rel),
            "file_size_bytes": st.st_size,
            "file_hash_sha256": file_hash,
            "encoding_detected": enc,
            "publication_date": None,
            "url": None,
            "extraction_tool": tool,
            "ocr_used": ocr_used,
            "ocr_confidence": None,
            "extraction_warnings": [],
        },
        "source_metadata": {
            "total_rows": total_rows,
            "rows_stored": total_rows,
            "truncated": False,
            "streamed": True,
        },
    }

    with open(output_path, "w", encoding="utf-8") as fout:
        # Fixed header + text
        fout.write(json.dumps(fixed_head, ensure_ascii=False)[:-1] + ",")  # drop closing '}'
        fout.write('\n"structured_data": [\n  {"headers": [], "rows": [\n')

        # Stream rows
        first = True
        for row in _iter_rows(filepath):
            if not first:
                fout.write(",\n    ")
            else:
                fout.write("    ")
                first = False
            json.dump(row, fout, ensure_ascii=False)

        fout.write("\n  ]}\n]")

        # Fixed tail (minus nothing — we already wrote leading '{')
        fout.write(", ")
        body_without_braces = json.dumps(fixed_tail, ensure_ascii=False)
        fout.write(body_without_braces[1:-1])  # strip outer { }
        fout.write("\n}\n")

    return {
        "filepath": filepath,
        "folder": folder_name,
        "status": "success",
        "processing_time_s": 0,
        "rows_total": total_rows,
    }


def write_standalone(filepath: Path, output_path: Path, datasets_dir: Path,
                     folder_name: str, subcategory: str, format_ext: str,
                     file_hash: str | None = None) -> int:
    """Convenience wrapper returning the row count (for direct CLI/testing)."""
    res = stream_rrf_to_json(filepath, output_path, datasets_dir, folder_name,
                             subcategory, format_ext, file_hash)
    return res["rows_total"]