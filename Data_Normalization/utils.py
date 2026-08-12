"""
MedGraphRAG Data Normalization — Utilities
Shared helpers: idempotency, duplicate detection, skip logic, path helpers.
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

from config import (
    SKIP_DIRS, SKIP_STEMS_CASE_INSENSITIVE, SKIP_FULL_NAMES_CASE_INSENSITIVE,
    SKIP_EXTENSIONS, SKIP_METADATA_NAMES, REVIEW_SKIP_NAMES, SKIP_PATH_PATTERNS,
)


def is_skippable(filepath: Path) -> tuple[bool, str]:
    """
    Check if a file should be skipped per the boilerplate SKIP list (§6).
    Returns (should_skip, reason).
    """
    name_lower = filepath.name.lower()
    stem_lower = filepath.stem.lower()
    path_str = str(filepath)

    # ── Explicit HuggingFace container scaffolding (blobs/refs/snapshots) ──
    for pattern in SKIP_PATH_PATTERNS:
        if pattern in path_str:
            return True, f"skip_huggingface:{pattern}"

    # Check skip directories in path
    for part in filepath.parts:
        if part in SKIP_DIRS:
            return True, f"skip_dir:{part}"

    # Check skip extensions
    if filepath.suffix.lower() in SKIP_EXTENSIONS:
        return True, f"skip_extension:{filepath.suffix}"

    # Check skip stems (e.g., "readme" matches "README.md")
    if stem_lower in SKIP_STEMS_CASE_INSENSITIVE:
        return True, f"skip_stem:{filepath.stem}"

    # Check skip full filenames (case-insensitive)
    if name_lower in SKIP_FULL_NAMES_CASE_INSENSITIVE:
        return True, f"skip_filename:{filepath.name}"

    # Check metadata files
    if filepath.name in SKIP_METADATA_NAMES:
        return True, f"skip_metadata:{filepath.name}"

    # Check review skip list
    if filepath.name in REVIEW_SKIP_NAMES:
        return True, f"skip_review:{filepath.name}"

    return False, ""


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def load_processed_set(logs_dir: Path) -> set:
    """
    Load the set of already-processed file hashes from processing_log.csv
    for idempotency (§9). Returns set of full relative paths (subpath/filename).
    """
    import csv as csv_mod
    processed = set()
    log_file = logs_dir / "processing_log.csv"
    if log_file.exists():
        with open(log_file, "r") as f:
            reader = csv_mod.reader(f)
            header = next(reader, None)  # skip header
            for row in reader:
                if len(row) >= 5:
                    status = row[4]
                    if status == "success":
                        # row = [filename, folder, subpath, format, status, ...]
                        filename = row[0]
                        subpath = row[2]
                        # Build full relative path: subpath/filename
                        full_rel = f"{subpath}/{filename}" if subpath else filename
                        processed.add(full_rel)
    return processed


def is_duplicate(file_hash: str, duplicate_map: dict) -> bool:
    """Check if a file hash is a known duplicate (§9)."""
    return file_hash in duplicate_map


def record_duplicate(file_hash: str, original_path: str, duplicate_path: str, duplicate_map: dict):
    """Record a duplicate mapping."""
    if file_hash not in duplicate_map:
        duplicate_map[file_hash] = []
    duplicate_map[file_hash].append({
        "original": original_path,
        "duplicate": duplicate_path,
    })


def save_duplicate_map(duplicate_map: dict, logs_dir: Path):
    """Save duplicate_map.json (§9)."""
    out = logs_dir / "duplicate_map.json"
    with open(out, "w") as f:
        json.dump(duplicate_map, f, indent=2)


def log_failed_file(
    filename: str, folder: str, subpath: str, format_ext: str,
    error: str, traceback_str: str, logs_dir: Path
):
    """Log a failed file to failed_files.jsonl (§11)."""
    entry = {
        "filename": filename,
        "folder": folder,
        "subpath": subpath,
        "format": format_ext,
        "error": error,
        "traceback": traceback_str,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    log_file = logs_dir / "failed_files.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


def get_output_path(filepath: Path, datasets_dir: Path, output_dir: Path) -> Path:
    """
    Compute output path: normalized/{source}/{subpath}/{stem}.json
    """
    rel = filepath.relative_to(datasets_dir)
    parts = list(rel.parts)
    stem = filepath.stem
    if len(parts) > 1:
        subpath = Path(*parts[:-1])
        return output_dir / subpath / f"{stem}.json"
    return output_dir / f"{stem}.json"


def get_folder_name(filepath: Path, datasets_dir: Path) -> str:
    """Get the top-level dataset folder name."""
    rel = filepath.relative_to(datasets_dir)
    return rel.parts[0] if rel.parts else "unknown"
