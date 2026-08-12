"""
MedGraphRAG Data Normalization — Main Pipeline (§2)
Orchestrates file discovery, format dispatch, parsing, and output.
"""

import gc
import json
import logging
import traceback
import sys
import shutil
import os
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv

from config import (
    DATASETS_DIR, OUTPUT_DIR, LOGS_DIR, CATEGORY_MAP,
    SCHEMA_VERSION, RUN_TIMESTAMP,
    MIN_FREE_SPACE_GB, WARN_FREE_SPACE_GB,
)
from parsers import get_parser
from utils import (
    is_skippable, compute_sha256, load_processed_set,
    is_duplicate, record_duplicate, save_duplicate_map,
    log_failed_file, get_output_path, get_folder_name,
)

logger = logging.getLogger(__name__)

# Stream source RRF-family files above this size instead of building full list
# in memory (avoids OOM on multi-GB UMLS files).
STREAM_MIN_BYTES = 5 * 1024 * 1024  # 5 MB


def _stream_candidate(filepath: Path, ext: str) -> bool:
    """Decide whether a file should take the streaming RRF writer path."""
    ext = ext.lower()
    is_rrf_ext = ext in (".rrf", ".crlf")
    is_extensionless = ext == ""
    if not (is_rrf_ext or is_extensionless):
        return False
    try:
        if filepath.stat().st_size < STREAM_MIN_BYTES:
            return False
    except OSError:
        return False
    if is_extensionless:
        # Only stream extensionless files that actually look pipe-delimited.
        try:
            with open(filepath, "rb") as f:
                head = f.read(2048)
            return b"|" in head
        except OSError:
            return False
    return True


def _display_format(ext: str, parsed: dict) -> str:
    """Resolve the human-readable format for a parsed file.

    Extensionless files have ext == "" (e.g. UMLS Semantic Network / Lexical
    RRF-family files). Derive a meaningful label from the parser that ran.
    """
    if ext:
        return ext.lstrip(".")
    tool = (parsed.get("metadata") or {}).get("extraction_tool", "")
    if tool == "csv+pipe":
        return "rrf"
    if tool == "text":
        return "txt"
    return ext.lstrip(".")


class NormalizationPipeline:
    """Main pipeline orchestrator — Step 0 reconciliation, Step 1 processing."""

    def __init__(self, max_workers: int = 4, force: bool = False, folder: str | None = None):
        self.datasets_dir = DATASETS_DIR
        self.output_dir = OUTPUT_DIR
        self.logs_dir = LOGS_DIR
        self.max_workers = max_workers
        self.force = force
        self.folder = folder  # optional — restrict to one top-level dataset folder

        # State
        self.processed_set = set()
        self.duplicate_map = {}
        self.stats = {
            "total": 0,
            "succeeded": 0,
            "skipped_processed": 0,
            "skipped_duplicate": 0,
            "skipped_boilerplate": 0,
            "failed": 0,
            "failure_list": [],
        }
        self.per_folder = {}
        self.per_format = {}
        self.processing_log_entries = []  # Track all entries for CSV (for summary at end)

        # Incremental CSV write — append one row per file, not a bulk rewrite at the end
        self._csv_path = self.logs_dir / "processing_log.csv"
        self._csv_fh = None  # Opened lazily in run()

        # Ensure output dirs exist
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def _check_disk_space(self) -> bool:
        """Check available disk space. Returns True if OK, False if critically low."""
        try:
            usage = shutil.disk_usage(self.output_dir)
            free_gb = usage.free / (1024 ** 3)
            total_gb = usage.total / (1024 ** 3)
            used_gb = usage.used / (1024 ** 3)
            pct = (usage.used / usage.total) * 100

            if free_gb < MIN_FREE_SPACE_GB:
                print(f"\n  ⛔ CRITICAL: Only {free_gb:.1f} GB free disk space!")
                print(f"     Need at least {MIN_FREE_SPACE_GB} GB to continue safely.")
                print(f"     Disk: {used_gb:.1f} / {total_gb:.1f} GB ({pct:.0f}% used)")
                return False
            elif free_gb < WARN_FREE_SPACE_GB:
                print(f"\n  ⚠️  WARNING: Only {free_gb:.1f} GB free disk space")
                print(f"     Disk: {used_gb:.1f} / {total_gb:.1f} GB ({pct:.0f}% used)")
            return True
        except Exception as e:
            logger.warning(f"Could not check disk space: {e}")
            return True  # Proceed if we can't check

    def collect_files(self) -> list[tuple[Path, str, dict]]:
        """
        Recursively walk all source folders and collect processable files.
        Returns list of (filepath, folder_name, info_dict).
        """
        files = []
        for folder_path in sorted(self.datasets_dir.iterdir()):
            if not folder_path.is_dir():
                continue
            if folder_path.name.startswith("."):
                continue
            if folder_path.name == "normalized":
                continue
            if self.folder and folder_path.name != self.folder:
                continue

            folder_name = folder_path.name
            for filepath in folder_path.rglob("*"):
                if not filepath.is_file():
                    continue

                # Skip boilerplate
                should_skip, reason = is_skippable(filepath)
                if should_skip:
                    continue

                files.append((filepath, folder_name, {}))

        return files

    def _prescan_duplicates(self, files: list[tuple[Path, str, dict]]) -> list[tuple[Path, str, dict]]:
        """
        Pre-scan: hash every candidate file once upfront, keep only the first
        occurrence per hash. Records all duplicates in duplicate_map.json.
        Skips already-processed files to avoid re-hashing large files.
        Stores computed hash in info dict so process_file can reuse it.
        """
        seen_hashes: dict[str, tuple[Path, str]] = {}  # hash -> (first_filepath, first_folder)
        deduped_files = []
        new_duplicates = 0
        processed_skipped = 0

        for filepath, folder_name, info in files:
            # Skip already-processed files BEFORE hashing
            if not self.force:
                rel_path = str(filepath.relative_to(self.datasets_dir))
                if rel_path in self.processed_set:
                    processed_skipped += 1
                    self.stats["skipped_processed"] += 1
                    continue

            file_hash = compute_sha256(filepath)

            if file_hash in seen_hashes:
                # This is a duplicate — record it but don't process
                original_path, original_folder = seen_hashes[file_hash]
                record_duplicate(
                    file_hash,
                    str(original_path.relative_to(self.datasets_dir)),
                    str(filepath.relative_to(self.datasets_dir)),
                    self.duplicate_map,
                )
                self.stats["skipped_duplicate"] += 1
                new_duplicates += 1
                continue

            # First occurrence — keep it + store hash for later reuse
            seen_hashes[file_hash] = (filepath, folder_name)
            info["sha256"] = file_hash  # So process_file doesn't re-hash
            deduped_files.append((filepath, folder_name, info))

        if new_duplicates > 0 or processed_skipped > 0:
            save_duplicate_map(self.duplicate_map, self.logs_dir)
            print(f"    Dedup: {new_duplicates} duplicate(s) removed, "
                  f"{processed_skipped} already-processed skipped, "
                  f"{len(deduped_files)} unique files to process")

        return deduped_files

    def process_file(self, filepath: Path, folder_name: str, file_hash: str | None = None) -> dict:
        """
        Process a single source file: parse → normalize → write JSON.
        Accepts optional precomputed file_hash (from prescan) to avoid re-hashing.
        Returns status dict with processing details.
        """
        ext = filepath.suffix.lower()
        stem = filepath.stem
        rel_path = filepath.relative_to(self.datasets_dir)
        subpath = str(Path(*rel_path.parts[:-1])) if len(rel_path.parts) > 1 else ""

        start_time = datetime.now(timezone.utc)

        # 1. Check idempotency — skip if already processed
        if not self.force:
            key = str(rel_path)
            if key in self.processed_set:
                return {
                    "filepath": filepath, "folder": folder_name,
                    "status": "skipped_processed", "processing_time_s": 0
                }

        # 2. Check duplicates by SHA-256 (use precomputed hash if available)
        if file_hash is None:
            file_hash = compute_sha256(filepath)
        if not self.force and is_duplicate(file_hash, self.duplicate_map):
            record_duplicate(file_hash, "", str(rel_path), self.duplicate_map)
            return {
                "filepath": filepath, "folder": folder_name,
                "status": "skipped_duplicate", "processing_time_s": 0
            }

        # 3. Get parser for this format
        parser = get_parser(ext)
        if parser is None:
            return {
                "filepath": filepath, "folder": folder_name,
                "status": "failed", "processing_time_s": 0,
                "error": f"No parser available for extension: {ext}",
            }

        # 3b. Large RRF-family files → stream directly (avoid building full list in RAM).
        if _stream_candidate(filepath, ext):
            return self._stream_rrf(filepath, folder_name, file_hash, rel_path, subpath)

        # 4. Parse the file
        try:
            parsed = parser(filepath)
        except Exception as e:
            tb = traceback.format_exc()
            log_failed_file(
                filepath.name, folder_name, subpath, ext,
                str(e), tb, self.logs_dir
            )
            return {
                "filepath": filepath, "folder": folder_name,
                "status": "failed", "processing_time_s": 0,
                "error": str(e),
            }

        if parsed is None or parsed.get("text_body") is None:
            log_failed_file(
                filepath.name, folder_name, subpath, ext,
                "Parser returned None", "", self.logs_dir
            )
            return {
                "filepath": filepath, "folder": folder_name,
                "status": "failed", "processing_time_s": 0,
                "error": "Parser returned None",
            }

        # 5. Determine subcategory from category map
        subcategory = CATEGORY_MAP.get(folder_name, "unknown")

        # 6. Build the output JSON using schema
        from schema import build_output_schema
        doc = build_output_schema(
            filepath=filepath,
            datasets_dir=self.datasets_dir,
            folder_name=folder_name,
            subcategory=subcategory,
            text_body=parsed.get("text_body"),
            text_title=parsed.get("text_title"),
            text_abstract=parsed.get("text_abstract"),
            structured_data=parsed.get("structured_data"),
            figures=parsed.get("figures"),
            page_count=parsed.get("page_count"),
            metadata=parsed.get("metadata", {}),
            source_metadata=parsed.get("source_metadata", {}),
            extraction_warnings=parsed.get("extraction_warnings", []),
            format_ext=_display_format(ext, parsed),
            file_hash=file_hash,  # Pass precomputed hash — avoid re-reading file
        )

        # 7. Write output
        extraction_warnings = parsed.get("extraction_warnings", [])
        output_path = get_output_path(filepath, self.datasets_dir, self.output_dir)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(doc, f, indent=2, ensure_ascii=False)
            # Free memory from parsed file — critical for large files
            del doc, parsed
            if filepath.stat().st_size > 100 * 1024 * 1024:  # > 100 MB
                gc.collect()
        except OSError as e:
            # Specifically handle disk space errors
            if "No space" in str(e) or "ENOSPC" in str(e):
                tb = traceback.format_exc()
                log_failed_file(
                    filepath.name, folder_name, subpath, ext,
                    f"DISK FULL: {e}", tb, self.logs_dir
                )
                print(f"\n  ⛔ DISK FULL — stopping pipeline to prevent data loss")
                raise SystemExit(1)
            tb = traceback.format_exc()
            log_failed_file(
                filepath.name, folder_name, subpath, ext,
                f"Write error: {e}", tb, self.logs_dir
            )
            return {
                "filepath": filepath, "folder": folder_name,
                "status": "failed", "processing_time_s": 0,
                "error": str(e),
            }
        except Exception as e:
            tb = traceback.format_exc()
            log_failed_file(
                filepath.name, folder_name, subpath, ext,
                f"Write error: {e}", tb, self.logs_dir
            )
            return {
                "filepath": filepath, "folder": folder_name,
                "status": "failed", "processing_time_s": 0,
                "error": str(e),
            }

        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

        return {
            "filepath": filepath, "folder": folder_name,
            "status": "success", "processing_time_s": elapsed,
            "extraction_warnings": extraction_warnings,
        }

    def _stream_rrf(self, filepath: Path, folder_name: str, file_hash: str | None,
                    rel_path, subpath) -> dict:
        """Stream a large RRF-family file to normalized JSON (row-by-row, low RAM).

        Returns a status dict compatible with process_file so it can be recorded
        and logged exactly like any other success/failure.
        """
        from parsers.rrf_stream import stream_rrf_to_json
        start = datetime.now(timezone.utc)
        ext = filepath.suffix.lower()
        subcategory = CATEGORY_MAP.get(folder_name, "unknown")
        output_path = get_output_path(filepath, self.datasets_dir, self.output_dir)
        fmt_ext = _display_format(ext, {"metadata": {"extraction_tool": "csv+pipe"}})
        try:
            stream_rrf_to_json(
                filepath, output_path, self.datasets_dir, folder_name,
                subcategory, fmt_ext, file_hash,
            )
        except Exception as e:
            tb = traceback.format_exc()
            log_failed_file(
                filepath.name, folder_name, subpath, ext,
                f"Stream error: {e}", tb, self.logs_dir
            )
            return {
                "filepath": filepath, "folder": folder_name,
                "status": "failed", "processing_time_s": 0,
                "error": str(e),
            }
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        return {
            "filepath": filepath, "folder": folder_name,
            "status": "success", "processing_time_s": elapsed,
        }

    def run(self):
        """Run the full normalization pipeline."""
        print("=" * 72)
        print(f"  MedGraphRAG Data Normalization v{SCHEMA_VERSION}")
        print(f"  Started: {RUN_TIMESTAMP}")
        print("=" * 72)

        # 0. Check disk space before starting
        if not self._check_disk_space():
            print("\n  Aborting due to insufficient disk space.")
            sys.exit(1)

        # 1. Load existing state for idempotency
        self.processed_set = load_processed_set(self.logs_dir)

        # Load existing duplicate map
        dup_map_path = self.logs_dir / "duplicate_map.json"
        if dup_map_path.exists():
            try:
                with open(dup_map_path) as f:
                    self.duplicate_map = json.load(f)
            except (json.JSONDecodeError, Exception):
                self.duplicate_map = {}

        # 2. Collect files
        print("\n  [Step 1] Collecting files...")
        all_files = self.collect_files()
        self.stats["total"] = len(all_files)
        print(f"    Found {len(all_files)} processable files")

        # Initialize CSV header (append rows incrementally from here)
        self._init_csv(force=self.force)

        # 2b. Pre-scan duplicates by SHA-256 (true dedup, not output-existence)
        all_files = self._prescan_duplicates(all_files)
        self.stats["total"] = len(all_files)
        print(f"    After dedup: {len(all_files)} unique files")

        # 3. Process files
        print(f"\n  [Step 2] Processing files ({self.max_workers} workers)...")
        processed = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.process_file, fp, fn, info.get("sha256")): (fp, fn)
                for fp, fn, info in all_files
            }

            for future in as_completed(futures):
                try:
                    result = future.result()
                except Exception as e:
                    fp, fn = futures[future]
                    result = {
                        "filepath": fp, "folder": fn,
                        "status": "failed", "processing_time_s": 0,
                        "error": f"Thread error: {e}",
                    }

                processed += 1
                self._record_result(result)

                # Progress every 100
                if processed % 100 == 0:
                    self._print_status_summary(prefix=f"    [{processed}/{self.stats['total']}] ")

                # Check disk space every 200 files
                if processed % 200 == 0:
                    if not self._check_disk_space():
                        print("\n  ⛔ Stopping pipeline — disk space critically low")
                        executor.shutdown(wait=False, cancel_futures=True)
                        break

        # 4. Save reports
        self._save_reports()

        # 5. Print final summary
        self._print_final_summary()

    def _record_result(self, result: dict):
        """Record a processing result into stats and processing log."""
        status = result["status"]
        folder = result["folder"]
        ext = result["filepath"].suffix.lower().lstrip(".")
        rel_path = result["filepath"].relative_to(self.datasets_dir)
        subpath = str(Path(*rel_path.parts[:-1])) if len(rel_path.parts) > 1 else ""

        # Track per-folder
        if folder not in self.per_folder:
            self.per_folder[folder] = {"total": 0, "success": 0, "failed": 0,
                                        "skipped_processed": 0, "skipped_duplicate": 0}
        self.per_folder[folder]["total"] += 1
        self.per_folder[folder][status] = self.per_folder[folder].get(status, 0) + 1

        # Track per-format
        if ext not in self.per_format:
            self.per_format[ext] = {"total": 0, "success": 0, "failed": 0}
        self.per_format[ext]["total"] += 1
        if status == "success":
            self.per_format[ext]["success"] += 1
        elif status == "failed":
            self.per_format[ext]["failed"] += 1

        # Global stats
        self.stats[status] = self.stats.get(status, 0) + 1
        if status == "failed":
            error = result.get("error", "Unknown error")
            self.stats["failure_list"].append({
                "filepath": str(result["filepath"]),
                "folder": folder,
                "error": error,
            })

        # Record for processing_log.csv — append one row immediately (not buffered)
        entry = {
            "filename": result["filepath"].name,
            "folder": folder,
            "subpath": subpath,
            "format": ext,
            "status": status,
            "processing_time_s": result.get("processing_time_s", 0),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.processing_log_entries.append(entry)  # keep in-memory for summary
        self._append_csv_row(entry)  # write to disk NOW — crash-safe

    def _init_csv(self, force: bool = False):
        """Write CSV header if file doesn't exist yet (or if force mode)."""
        if force or not self._csv_path.exists():
            with open(self._csv_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["filename", "folder", "subpath", "format",
                                 "status", "processing_time_seconds", "timestamp"])

    def _append_csv_row(self, entry: dict):
        """Append a single row to the CSV (true incremental append)."""
        try:
            with open(self._csv_path, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    entry["filename"], entry["folder"], entry["subpath"],
                    entry["format"], entry["status"],
                    entry.get("processing_time_s", 0), entry.get("timestamp", ""),
                ])
        except Exception as e:
            logger.warning(f"Failed to append CSV row: {e}")

    def _save_reports(self):
        """Save processing_log.csv, failed_files.jsonl, summary_report.json, duplicate_map.json."""
        logs_dir = self.logs_dir

        # processing_log.csv — already written incrementally via _append_csv_row()

        # summary_report.json
        report = {
            "schema_version": SCHEMA_VERSION,
            "run_timestamp": RUN_TIMESTAMP,
            "total_files": self.stats["total"],
            "succeeded": self.stats.get("succeeded", 0),
            "skipped_processed": self.stats.get("skipped_processed", 0),
            "skipped_duplicate": self.stats.get("skipped_duplicate", 0),
            "failed": self.stats.get("failed", 0),
            "failure_list": self.stats["failure_list"][:100],
            "per_folder": self.per_folder,
            "per_format": self.per_format,
        }
        with open(logs_dir / "summary_report.json", "w") as f:
            json.dump(report, f, indent=2)

        # Save duplicate_map
        save_duplicate_map(self.duplicate_map, logs_dir)

        print(f"\n    Reports saved to {logs_dir}/")

    def _print_status_summary(self, prefix: str = ""):
        """Print a one-line status summary."""
        s = self.stats
        print(f"{prefix}Success: {s.get('succeeded',0)} | "
              f"Failed: {s.get('failed',0)} | "
              f"Skipped(proc): {s.get('skipped_processed',0)} | "
              f"Skipped(dup): {s.get('skipped_duplicate',0)}")

    def _print_final_summary(self):
        """Print the final summary report to console."""
        s = self.stats
        print("\n" + "=" * 72)
        print("  NORMALIZATION COMPLETE")
        print("=" * 72)
        print(f"  Total:         {s['total']}")
        print(f"  Succeeded:     {s.get('succeeded', 0)}")
        print(f"  Skipped (processed): {s.get('skipped_processed', 0)}")
        print(f"  Skipped (duplicate): {s.get('skipped_duplicate', 0)}")
        print(f"  Failed:        {s.get('failed', 0)}")
        if s.get("failure_list"):
            print("\n  Failure list:")
            for f in s["failure_list"][:20]:
                print(f"    - {f['folder']}/{f['filepath']}: {f['error']}")
            if len(s["failure_list"]) > 20:
                print(f"    ... and {len(s['failure_list']) - 20} more")
        print("=" * 72)
