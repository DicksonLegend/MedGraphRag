"""
OWL parser — handles both RDF/XML and Functional Syntax.
Memory-safe: caps body text for large files.
DocumentOntology.owl uses Functional Syntax (Prefix(...) / Declaration(...) format).
"""

from pathlib import Path
import xmltodict

from config import LARGE_FILE_THRESHOLD_BYTES, MAX_TEXT_BODY_CHARS


def _is_functional_syntax(content: str) -> bool:
    """Detect if OWL is in Functional Syntax (starts with Prefix(...) or Ontology(...))."""
    content = content.lstrip("﻿")
    stripped = content.strip()
    return stripped.startswith("Prefix(") or stripped.startswith("Ontology(")


def _parse_functional_syntax(filepath: Path) -> dict:
    """
    Parse OWL Functional Syntax — extract declarations and annotations as text.
    Memory-safe: streams lines for large files.
    """
    file_size = filepath.stat().st_size
    is_large = file_size > LARGE_FILE_THRESHOLD_BYTES
    max_body_chars = MAX_TEXT_BODY_CHARS

    body_parts = []
    declarations = 0
    annotations = 0
    total_lines = 0
    body_bytes = 0
    truncated = False

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            total_lines += 1
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("Prefix("):
                if not truncated:
                    body_parts.append(stripped)
                    body_bytes += len(stripped) + 1
            elif stripped.startswith("Ontology("):
                if not truncated:
                    body_parts.append(stripped)
                    body_bytes += len(stripped) + 1
            elif stripped.startswith("Declaration("):
                declarations += 1
                if not truncated:
                    body_parts.append(stripped)
                    body_bytes += len(stripped) + 1
            elif stripped.startswith("Annotation("):
                annotations += 1
                if not truncated:
                    body_parts.append(stripped)
                    body_bytes += len(stripped) + 1

            # Check cap for large files
            if is_large and not truncated and body_bytes > max_body_chars:
                truncated = True
                body_parts.append(
                    f"\n<!-- TRUNCATED at {max_body_chars} chars; "
                    f"total {total_lines} lines, {declarations} declarations -->"
                )

    body = "\n".join(body_parts)

    warnings = ["OWL Functional Syntax — parsed as structured text"]
    if truncated:
        warnings.append(f"Truncated: {file_size} bytes → {len(body)} chars stored")

    return {
        "text_body": body,
        "text_title": filepath.stem,
        "text_abstract": None,
        "page_count": None,
        "structured_data": [],
        "figures": [],
        "metadata": {"extraction_tool": "owl_functional_parser", "ocr_used": False},
        "source_metadata": {
            "format": "OWL Functional Syntax",
            "num_declarations": declarations,
            "num_annotations": annotations,
            "total_lines": total_lines,
            "truncated": truncated,
            "original_size_bytes": file_size,
        },
        "extraction_warnings": warnings,
    }


def _parse_xml_owl(filepath: Path) -> dict:
    """Parse OWL in RDF/XML format using xmltodict. Caps body for large files."""
    file_size = filepath.stat().st_size
    is_large = file_size > LARGE_FILE_THRESHOLD_BYTES

    with open(filepath, "rb") as f:
        data = xmltodict.parse(f)

    body = str(data)

    warnings = []
    if is_large and len(body) > MAX_TEXT_BODY_CHARS:
        body = body[:MAX_TEXT_BODY_CHARS]
        warnings.append(f"Body truncated: {file_size} bytes → {MAX_TEXT_BODY_CHARS} chars")

    return {
        "text_body": body,
        "text_title": filepath.stem,
        "text_abstract": None,
        "page_count": None,
        "structured_data": [],
        "figures": [],
        "metadata": {"extraction_tool": "xmltodict", "ocr_used": False},
        "source_metadata": data if isinstance(data, dict) and not is_large else {},
        "extraction_warnings": warnings,
    }


def parse_owl(filepath: Path) -> dict:
    """Parse an OWL file — detects format and routes accordingly."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            first_2k = f.read(2000)

        if _is_functional_syntax(first_2k):
            return _parse_functional_syntax(filepath)
        else:
            return _parse_xml_owl(filepath)

    except Exception as e:
        return {
            "text_body": None,
            "text_title": None,
            "text_abstract": None,
            "page_count": None,
            "structured_data": [],
            "figures": [],
            "metadata": {"extraction_tool": "owl_parser", "ocr_used": False},
            "source_metadata": {},
            "extraction_warnings": [f"OWL parse error: {e}"],
        }
