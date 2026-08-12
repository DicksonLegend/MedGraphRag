"""
MedGraphRAG Data Normalization — JSON Schema v1.2
Defines the output schema structure and validation.
"""

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import chardet

from config import SCHEMA_VERSION


def compute_file_hash(filepath: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def detect_encoding(filepath: Path) -> str:
    """Detect file encoding using chardet."""
    try:
        with open(filepath, "rb") as f:
            raw = f.read(10000)
        result = chardet.detect(raw)
        return result.get("encoding", "utf-8") or "utf-8"
    except Exception:
        return "utf-8"


def compute_subpath(filepath: Path, datasets_dir: Path) -> str:
    """
    Compute the relative subpath from the dataset root.
    e.g. Research_papers/PubMed/Abstracts/Alzheimers/PMID_12345.json
    """
    try:
        rel = filepath.relative_to(datasets_dir)
        parts = list(rel.parts)
        # Return everything except the filename itself
        return str(Path(*parts[:-1])) if len(parts) > 1 else ""
    except ValueError:
        return ""


def make_document_id(filepath: Path, datasets_dir: Path) -> str:
    """
    Create document_id: {source}/{subpath}/{stem}
    e.g. Research_papers/PubMed/Abstracts/Alzheimers/PMID_12345
    """
    rel = filepath.relative_to(datasets_dir)
    parts = list(rel.parts)
    # Remove extension from stem
    stem = filepath.stem
    if len(parts) > 1:
        return str(Path(*parts[:-1])) / stem
    return stem


def build_output_schema(
    filepath: Path,
    datasets_dir: Path,
    folder_name: str,
    subcategory: str,
    text_body: str = None,
    text_title: str = None,
    text_abstract: str = None,
    structured_data: list = None,
    figures: list = None,
    page_count: int = None,
    metadata: dict = None,
    source_metadata: dict = None,
    extraction_warnings: list = None,
    format_ext: str = None,
    language: str = None,
    file_hash: str = None,  # Precomputed hash (avoid re-reading)
) -> dict:
    """
    Build a normalized JSON document following schema v1.2.
    One JSON per leaf source file — never merged.
    Accepts optional precomputed file_hash to avoid re-reading large files.
    """
    rel = filepath.relative_to(datasets_dir)
    parts = list(rel.parts)
    # subpath excludes the top-level folder name (parts[0]) and the filename
    subpath = str(Path(*parts[1:-1])) if len(parts) > 2 else ""
    stem = filepath.stem

    file_stat = filepath.stat()
    file_size = file_stat.st_size
    # Only compute hash if not provided (avoids re-reading large files)
    file_hash = file_hash or compute_file_hash(filepath)
    enc = detect_encoding(filepath)
    doc_id = str(Path(folder_name) / subpath / stem) if subpath else str(Path(folder_name) / stem)

    # Pull author / publication_date / url from source_metadata (populated by parsers)
    src = source_metadata or {}
    author = src.get("author")
    publication_date = src.get("publication_date")
    url = src.get("url")

    # Build the document
    doc = {
        "schema_version": SCHEMA_VERSION,
        "document_id": doc_id,
        "source": folder_name,
        "subpath": subpath,
        "subcategory": subcategory,
        "dataset_version": None,
        "title": text_title,
        "author": author,
        "language": language,
        "format": format_ext or filepath.suffix.lstrip("."),
        "category": FORMAT_CATEGORY_OVERRIDES.get(folder_name, {}).get(
            format_ext, subcategory
        ),
        "text": {
            "title": text_title,
            "abstract": text_abstract,
            "body": text_body,
        },
        "structured_data": structured_data or [],
        "figures": figures or [],
        "page_count": page_count,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "original_path": str(rel),
            "file_size_bytes": file_size,
            "file_hash_sha256": file_hash,
            "encoding_detected": enc,
            "publication_date": publication_date,
            "url": url,
            "extraction_tool": metadata.get("extraction_tool", None) if metadata else None,
            "ocr_used": metadata.get("ocr_used", False) if metadata else False,
            "ocr_confidence": metadata.get("ocr_confidence", None) if metadata else None,
            "extraction_warnings": extraction_warnings or [],
        },
        "source_metadata": src,
    }
    return doc


# Category override mapping for output.category field
FORMAT_CATEGORY_OVERRIDES = {
    "Research_papers": {
        ".json": "research_paper",
        ".xml": "research_paper",
        ".csv": "research_paper",
        ".pdf": "research_paper",
    },
    "Clinical_practice_guidlines": {
        ".json": "guideline",
        ".csv": "guideline",
        ".html": "guideline",
        ".pdf": "guideline",
        ".jsonl": "guideline",
    },
    "BioASQ": {".json": "evidence_qa"},
    "Disease_knowledge": {".xml": "disease"},
    "Medical_ontologies": {".txt": "ontology", ".json": "ontology", ".owl": "ontology"},
    "Drug_database": {".tsv": "drug", ".xml": "drug", ".rrf": "drug", ".txt": "drug"},
    "Medical_books": {".jsonl": "textbook", ".txt": "textbook"},
    "Lab_rev_data": {".csv": "lab_reference", ".txt": "lab_reference", ".owl": "lab_reference", ".xlsx": "lab_reference"},
    "datasets--openlifescienceai--medmcqa": {".parquet": "qa_benchmark"},
    "MedQA-USMLE": {".parquet": "qa_benchmark"},
    "PubMedQA": {".parquet": "qa_benchmark"},
}
