"""
MedGraphRAG Data Normalization — Entry Point
Usage: python run.py [--force] [--workers N]
"""

import argparse
import logging
import sys
from pathlib import Path

# Ensure ./ is on sys.path
sys.path.insert(0, str(Path(__file__).parent))

from pipeline import NormalizationPipeline
from config import DATASETS_DIR, OUTPUT_DIR


def main():
    parser = argparse.ArgumentParser(
        description="MedGraphRAG Data Normalization Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py                    # Normal run (skip already-processed)
  python run.py --force            # Force reprocess all files
  python run.py --workers 8        # Process with 8 worker threads
  python run.py --dry-run          # Count files (Step 0) without processing
        """,
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Force reprocess all files (ignore idempotency)"
    )
    parser.add_argument(
        "--workers", type=int, default=4,
        help="Number of worker threads (default: 4)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Count and list files without processing"
    )
    parser.add_argument(
        "--folder", default=None,
        help="Restrict processing to one top-level dataset folder (for scoped tests)"
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)"
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Verify paths
    if not DATASETS_DIR.exists():
        print(f"ERROR: Datasets directory not found: {DATASETS_DIR}")
        sys.exit(1)

    print(f"MedGraphRAG Data Normalization Pipeline")
    print(f"  Datasets: {DATASETS_DIR}")
    print(f"  Output:   {OUTPUT_DIR}")
    print(f"  Workers:  {args.workers}")
    print()

    pipeline = NormalizationPipeline(
        max_workers=args.workers,
        force=args.force,
        folder=args.folder,
    )

    if args.folder:
        print(f"  Scope:    {args.folder}")

    if args.dry_run:
        print("[DRY RUN] Collecting files...")
        files = pipeline.collect_files()
        print(f"\nTotal processable files: {len(files)}")
        print("\nPer-folder breakdown:")
        folder_counts = {}
        format_counts = {}
        for fp, fn, _ in files:
            folder_counts[fn] = folder_counts.get(fn, 0) + 1
            ext = fp.suffix.lower()
            format_counts[ext] = format_counts.get(ext, 0) + 1
        for folder in sorted(folder_counts.keys()):
            print(f"  {folder}: {folder_counts[folder]}")
        print("\nPer-format breakdown:")
        for fmt in sorted(format_counts.keys()):
            print(f"  {fmt}: {format_counts[fmt]}")
        return

    pipeline.run()


if __name__ == "__main__":
    main()
