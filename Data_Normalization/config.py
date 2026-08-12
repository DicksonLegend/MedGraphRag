"""
MedGraphRAG Data Normalization — Configuration
All constants, paths, category maps, skip lists, and schema version.
"""

from pathlib import Path
from datetime import datetime, timezone

# ──────────────────────────────────────────────
# Paths (§0)
# ──────────────────────────────────────────────
PROJECT_ROOT   = Path("/home/dicksone/Documents/MedGraphRag")
DATASETS_DIR   = PROJECT_ROOT / "Datasets"
OUTPUT_DIR     = DATASETS_DIR / "normalized"
LOGS_DIR       = OUTPUT_DIR / "_logs"
SCHEMA_VERSION = "1.2"

# ──────────────────────────────────────────────
# Timestamp for the run (lazy — computed once at import time)
# ──────────────────────────────────────────────
RUN_TIMESTAMP = datetime.now(timezone.utc).isoformat()

# ──────────────────────────────────────────────
# Disk space safety thresholds
# ──────────────────────────────────────────────
MIN_FREE_SPACE_GB = 2          # Stop if less than 2 GB free
WARN_FREE_SPACE_GB = 5        # Warn if less than 5 GB free

# ──────────────────────────────────────────────
# Category map (§7) — folder → subcategory
# ──────────────────────────────────────────────
CATEGORY_MAP = {
    "BioASQ":                                    "evidence_qa",
    "clinical_manuals":                          "clinical_reference",
    "Clinical_practice_guidlines":               "guideline",
    "datasets--openlifescienceai--medmcqa":       "qa_benchmark",
    "Disease_knowledge":                         "disease",
    "Drug_database":                             "drug",
    "Lab_rev_data":                              "lab_reference",
    "Medical_books":                             "textbook",
    "Medical_ontologies":                        "ontology",
    "MedQA-USMLE":                               "qa_benchmark",
    "PubMedQA":                                  "qa_benchmark",
    "Research_papers":                           "research_paper",
    "UMLS Output":                               "ontology",
}

# ──────────────────────────────────────────────
# Boilerplate SKIP list (§6)
# ──────────────────────────────────────────────
SKIP_DIRS = {".cache", ".git", ".huggingface", "__pycache__", "blobs", "refs"}

# Explicit path patterns to always skip (HuggingFace container scaffolding)
SKIP_PATH_PATTERNS = [
    "/blobs/", "/refs/", "/.huggingface/", "/snapshots/",
    # UMLS: LVG Lexical Tools programmer site, program binaries, & compiled DBs — not medical data
    "/UMLS Output/LEX/DOCS/",
    "/UMLS Output/LEX/LEX_PGMS/",
    "/UMLS Output/LEX/LEX_DB/",
    "/UMLS Output/LEX/MISC/",
    "/UMLS Output/LEX/NUMBERS/",
    "/UMLS Output/LEX/VERB_COMPLEMENTS/",
]

SKIP_STEMS_CASE_INSENSITIVE = {
    "readme", "license", "licence", "citation",
}

SKIP_FULL_NAMES_CASE_INSENSITIVE = {
    ".gitattributes", ".gitignore", ".ds_store", "thumbs.db",
    "dataset_info.json", "dataset_dict.json", "config.json",
}

SKIP_EXTENSIONS = {
    ".py", ".pyc", ".sh", ".bat", ".cmd", ".exe", ".dll", ".so", ".dylib",
    ".o", ".a", ".ipynb", ".sfv", ".crc", ".md5", ".sha1", ".sha256",
    ".sha512", ".sig", ".asc", ".lock", ".toml", ".cfg", ".ini",
    ".yml", ".yaml", ".css", ".js", ".ts", ".map",
    ".svg", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp",
    ".woff", ".woff2", ".ttf", ".eot",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
    # Schema/script files — not source data
    ".ctl", ".xsd", ".dtd", ".sql", ".log", ".xslt",
    # CRLF line-ending duplicate (e.g. UMLS LRFIL.crlf) — collides with the
    # extensionless original; skip to avoid overwriting it in the output tree.
    ".crlf",
}

# Additional boilerplate patterns
SKIP_EXTENSIONS.update({".cff"})

# ──────────────────────────────────────────────
# REVIEW list → skip all except DocumentOntology.owl
# ──────────────────────────────────────────────
REVIEW_SKIP_NAMES = {
    "open_guidelines.jsonl",   # clinical review
    "summary.json",           # PMC metadata review
}

# ──────────────────────────────────────────────
# Known non-source metadata files to skip
# ──────────────────────────────────────────────
SKIP_METADATA_NAMES = {
    "removed_files.csv",
    "removed_files_20260720_155732.csv",
    "download_failed.csv",
    "download_success.csv",
    "CACHEDIR.TAG",
}

# ──────────────────────────────────────────────
# STREAMING list — XML files > 500 MB
# ──────────────────────────────────────────────
STREAMING_XML_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB

# ──────────────────────────────────────────────
# Huge files — skip entirely (archives to unpack)
# ──────────────────────────────────────────────
HUGE_FILE_THRESHOLD_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB

# ──────────────────────────────────────────────
# Memory-safe limits — prevent OOM crashes
# ──────────────────────────────────────────────
LARGE_FILE_THRESHOLD_BYTES  = 100 * 1024 * 1024   # 100 MB — parsers switch to truncated mode
MAX_TEXT_BODY_CHARS         = 50 * 1024 * 1024    # 50 MB  — text_body capped per file
MAX_STRUCTURED_DATA_ROWS    = 100_000              # 100K  — rows in structured_data capped
MAX_JSONL_LINES             = 50_000               # 50K   — lines parsed from JSONL files
MAX_CSV_PREVIEW_ROWS        = 500                  # 500   — rows in text_body preview

# ──────────────────────────────────────────────
# Container detection — archives to unpack
# ──────────────────────────────────────────────
ARCHIVE_EXTENSIONS = {".zip", ".tar", ".tar.gz", ".tgz", ".gz", ".bz2", ".xz", ".7z", ".rar"}

# ──────────────────────────────────────────────
# Per-folder subcategory overrides for text formats
# ──────────────────────────────────────────────
FOLDER_SUBCATEGORY_OVERRIDES = {
    "Research_papers": {
        ".json": "research_paper",
        ".xml":  "research_paper",
        ".csv":  "research_paper",
    },
    "Clinical_practice_guidlines": {
        ".json": "guideline",
        ".csv":  "guideline",
        ".html": "guideline",
        ".jsonl": "guideline",
    },
    "BioASQ": {
        ".json": "evidence_qa",
    },
    "Disease_knowledge": {
        ".xml": "disease",
    },
    "Medical_ontologies": {
        ".txt": "ontology",
        ".json": "ontology",
        ".owl": "ontology",
    },
    "Drug_database": {
        ".tsv": "drug",
        ".xml": "drug",
        ".rrf": "drug",
        ".sql": "drug",
        ".txt": "drug",
    },
    "Medical_books": {
        ".jsonl": "textbook",
        ".txt": "textbook",
    },
    "Lab_rev_data": {
        ".csv": "lab_reference",
        ".txt": "lab_reference",
        ".xml": "lab_reference",
        ".owl": "lab_reference",
        ".xlsx": "lab_reference",
    },
    "datasets--openlifescienceai--medmcqa": {
        ".parquet": "qa_benchmark",
    },
    "MedQA-USMLE": {
        ".parquet": "qa_benchmark",
    },
    "PubMedQA": {
        ".parquet": "qa_benchmark",
    },
}
