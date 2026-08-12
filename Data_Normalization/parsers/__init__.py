"""
MedGraphRAG Data Normalization — Parsers Package
Dispatch: format → parser module. One parser per file format (§2).
"""

from pathlib import Path

from parsers.pdf_parser import parse_pdf
from parsers.docx_parser import parse_docx
from parsers.pptx_parser import parse_pptx
from parsers.image_parser import parse_image
from parsers.xlsx_parser import parse_xlsx
from parsers.csv_parser import parse_csv
from parsers.tsv_parser import parse_tsv
from parsers.parquet_parser import parse_parquet
from parsers.json_parser import parse_json
from parsers.jsonl_parser import parse_jsonl
from parsers.xml_parser import parse_xml
from parsers.html_parser import parse_html
from parsers.txt_parser import parse_txt
from parsers.rrf_parser import parse_rrf
from parsers.owl_parser import parse_owl
from parsers.archive_parser import parse_archive

def parse_extensionless(filepath: Path) -> dict:
    """Parse an extensionless file by peeking at its content.

    Most extensionless medical-data files (UMLS RRF-family: Semantic Network
    NET/SR*, lexical LEX/LR*) are pipe-delimited — route them to the RRF
    parser. Fall back to plain-text for anything else.
    """
    try:
        with open(filepath, "rb") as f:
            head = f.read(4096)
    except OSError as e:
        return {
            "text_body": None,
            "text_abstract": None,
            "text_title": None,
            "page_count": None,
            "structured_data": [],
            "figures": [],
            "metadata": {"extraction_tool": "extensionless-sniff", "ocr_used": False},
            "source_metadata": {},
            "extraction_warnings": [f"unreadable file in sniff: {e}"],
        }

    # Binary / NUL bytes → not text, not parseable as RRF
    if b"\x00" in head:
        return _empty("binary/extensionless file")

    is_pipe = b"|" in head
    if is_pipe:
        return parse_rrf(filepath)
    # Otherwise treat as plain text (README-ish, etc.)
    return parse_txt(filepath)


def _empty(err: str) -> dict:
    """Return a safe 'empty' parser result for unrecognized extensionless files."""
    return {
        "text_body": None,
        "text_abstract": None,
        "text_title": None,
        "page_count": None,
        "structured_data": [],
        "figures": [],
        "metadata": {"extraction_tool": "extensionless-sniff", "ocr_used": False},
        "source_metadata": {},
        "extraction_warnings": [err],
    }


def get_parser(extension: str):
    """Get the parser function for a given file extension."""
    ext = extension.lower()
    if ext == "":
        return parse_extensionless
    return PARSERS.get(ext)


def get_all_formats() -> list[str]:
    """Return all supported file extensions."""
    return list(PARSERS.keys()) + [""]

# Extension → parser function mapping
PARSERS = {
    ".pdf":     parse_pdf,
    ".docx":    parse_docx,
    ".pptx":    parse_pptx,
    ".png":     parse_image,
    ".jpg":     parse_image,
    ".jpeg":    parse_image,
    ".tiff":    parse_image,
    ".bmp":     parse_image,
    ".gif":     parse_image,
    ".xlsx":    parse_xlsx,
    ".xls":     parse_xlsx,
    ".csv":     parse_csv,
    ".parquet": parse_parquet,
    ".json":    parse_json,
    ".jsonl":   parse_jsonl,
    ".xml":     parse_xml,
    ".html":    parse_html,
    ".htm":     parse_html,
    ".txt":     parse_txt,
    ".md":      parse_txt,
    ".rrf":     parse_rrf,
    ".owl":     parse_owl,
    ".tsv":     parse_tsv,
    ".zip":     parse_archive,
}
