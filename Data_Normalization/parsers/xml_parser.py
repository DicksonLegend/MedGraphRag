"""
XML parser — xmltodict with streaming for large files (DrugBank 1.6 GB)
Memory-safe: caps parsed elements and body text for large files.
"""

import gc
from pathlib import Path
import xmltodict

from config import (
    LARGE_FILE_THRESHOLD_BYTES,
    MAX_STRUCTURED_DATA_ROWS,
    MAX_TEXT_BODY_CHARS,
)


def _parse_xml_full(filepath: Path) -> dict:
    """Parse an XML file fully into a dict using xmltodict."""
    with open(filepath, "rb") as f:
        data = xmltodict.parse(f)
    return data


def _parse_xml_streaming(
    filepath: Path,
    target_tag: str = "drug",
    max_items: int = MAX_STRUCTURED_DATA_ROWS,
) -> dict:
    """
    Streaming XML parse for large files.
    Caps results at max_items to prevent OOM.
    Uses iterparse to avoid loading entire file into memory.
    """
    import xml.etree.ElementTree as ET

    results = []
    total_count = 0
    truncated = False
    gc_interval = max(1, max_items // 10)  # gc every ~10% of capacity

    for event, elem in ET.iterparse(str(filepath), events=("end",)):
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag == target_tag:
            total_count += 1
            if len(results) < max_items:
                item = _element_to_dict(elem)
                results.append(item)
            elif not truncated:
                truncated = True
            elem.clear()
            # Periodic garbage collection to free ElementTree nodes
            if total_count % gc_interval == 0:
                gc.collect()

    return {
        f"{target_tag}s": results,
        "_streaming": True,
        "_total_elements": total_count,
        "_truncated": truncated,
    }


def _element_to_dict(elem) -> dict:
    """Convert an ElementTree element to a dict. Memory-optimized."""
    result = {}
    for key, val in elem.attrib.items():
        result[f"@{key}"] = val
    children = list(elem)
    if children:
        for child in children:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            child_dict = _element_to_dict(child)
            if tag in result:
                if not isinstance(result[tag], list):
                    result[tag] = [result[tag]]
                result[tag].append(child_dict)
            else:
                result[tag] = child_dict
    text = (elem.text or "").strip()
    if text and not result:
        return text
    if text:
        result["#text"] = text
    return result


def parse_xml(filepath: Path) -> dict:
    """
    Parse an XML file.
    - Small files (< 100 MB): full xmltodict parse, handles JATS articles
    - Large files (>= 100 MB): streaming iterparse, truncated output
    """
    try:
        size = filepath.stat().st_size
        is_large = size > LARGE_FILE_THRESHOLD_BYTES
        warnings = []

        if is_large:
            # Streaming mode for large files (e.g., DrugBank 1.6 GB)
            data = _parse_xml_streaming(filepath)
            body = str(data)
            total_elements = data.get("_total_elements", 0)
            truncated = data.get("_truncated", False)
            warnings.append(
                f"Streaming parse used: file was {size / 1024 / 1024:.1f} MB"
            )
            if truncated:
                warnings.append(
                    f"XML elements truncated: {total_elements} total → {MAX_STRUCTURED_DATA_ROWS} stored"
                )
            # Cap body length
            if len(body) > MAX_TEXT_BODY_CHARS:
                body = body[:MAX_TEXT_BODY_CHARS]
                warnings.append(
                    f"Body truncated: {size} bytes → {MAX_TEXT_BODY_CHARS} chars"
                )

            title = filepath.stem
            abstract = None
            # Don't store full data dict — too large
            source_metadata = {
                "streaming": True,
                "total_elements": total_elements,
                "truncated": truncated,
                "original_size_bytes": size,
            }
        else:
            # Full parse with xmltodict
            data = _parse_xml_full(filepath)

            root_key = next(iter(data)) if isinstance(data, dict) else ""
            is_jats = root_key in ("article",)

            if is_jats:
                title, abstract, body = _extract_jats(data)
                # If JATS extraction failed to get body, fall back to raw XML
                if body is None:
                    body = str(data)
                    warnings.append("JATS extraction failed — fell back to raw XML")
                # Ensure title fallback
                if title is None:
                    title = filepath.stem
            else:
                body = str(data)
                title = filepath.stem
                abstract = None

            # Cap body
            if body and len(body) > MAX_TEXT_BODY_CHARS:
                body = body[:MAX_TEXT_BODY_CHARS]
                warnings.append(
                    f"Body truncated: {size} bytes → {MAX_TEXT_BODY_CHARS} chars"
                )
                source_metadata = {"truncated": True, "original_size_bytes": size}
            else:
                source_metadata = {}

        return {
            "text_body": body,
            "text_title": title,
            "text_abstract": abstract,
            "page_count": None,
            "structured_data": [],
            "figures": [],
            "metadata": {"extraction_tool": "xmltodict", "ocr_used": False},
            "source_metadata": source_metadata,
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
            "metadata": {"extraction_tool": "xmltodict", "ocr_used": False},
            "source_metadata": {},
            "extraction_warnings": [f"XML parse error: {e}"],
        }


def _extract_jats(data: dict) -> tuple:
    """Extract title, abstract, body from JATS/NLM XML."""
    title = None
    abstract = None
    body = None

    try:
        article = data.get("article", {})
        front = article.get("front", {})

        # Title
        article_meta = front.get("article-meta", {})
        title_group = article_meta.get("title-group", {})
        if isinstance(title_group, dict):
            article_title = title_group.get("article-title", None)
            if isinstance(article_title, str):
                title = article_title
            elif isinstance(article_title, dict):
                title = article_title.get("#text", None) or str(article_title)

        # Abstract
        abstract_elem = article_meta.get("abstract", None)
        if abstract_elem:
            if isinstance(abstract_elem, dict):
                # Simple abstract with <p> children
                p = abstract_elem.get("p", None)
                if isinstance(p, str):
                    abstract = p
                elif isinstance(p, list):
                    abstract = " ".join([x.get("#text", x) if isinstance(x, dict) else str(x) for x in p])
                elif isinstance(p, dict):
                    abstract = p.get("#text", str(p))
            elif isinstance(abstract_elem, str):
                abstract = abstract_elem

        # Body
        body_elem = article.get("body", None)
        if body_elem:
            if isinstance(body_elem, dict):
                # Extract all text from body
                body_parts = []
                _extract_text(body_elem, body_parts)
                body = "\n".join(body_parts)
            elif isinstance(body_elem, str):
                body = body_elem
    except Exception:
        pass

    return title, abstract, body


def _extract_text(node: dict, parts: list, depth: int = 0):
    """Recursively extract text from a nested dict (JATS body)."""
    if not isinstance(node, dict):
        if isinstance(node, str):
            parts.append(node.strip())
        return

    for key, value in node.items():
        if key == "#text" and isinstance(value, str):
            parts.append(value.strip())
        elif key in ("p", "title", "sec", "label", "list-item", "def-item"):
            if isinstance(value, list):
                for item in value:
                    _extract_text(item if isinstance(item, dict) else {"#text": str(item)}, parts, depth + 1)
            elif isinstance(value, dict):
                _extract_text(value, parts, depth + 1)
            elif isinstance(value, str):
                parts.append(value.strip())
        elif isinstance(value, (dict, list)):
            if isinstance(value, list):
                for item in value:
                    _extract_text(item if isinstance(item, dict) else {"#text": str(item)}, parts, depth + 1)
            else:
                _extract_text(value, parts, depth + 1)
