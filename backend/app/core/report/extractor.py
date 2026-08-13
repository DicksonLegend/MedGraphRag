"""
MedGraphRAG Backend — Stage B: Lab Value Extractor
===================================================
Extracts LabValue records from ParsedReport.
Primary: Rule/regex-based extraction for clean text lines and table rows.
Fallback: Reuses the existing Qwen2.5-7B LLM loader singleton for unstructured reports.

SAFETY RULE: Exact value preservation — never alter, round, or reformat numeric values or units.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.core.report.schemas import LabValue, ParsedReport
from app.core.llm.llm_loader import get_llm

logger = logging.getLogger(__name__)

# Medical lab value line regex matching pattern
# Examples:
#   Potassium: 6.8 mmol/L (3.5 - 5.1)
#   Hemoglobin   8.0   g/dL   12.0-16.0
#   Creatinine (KFT): 354 µmol/L
#   WBC Count: 14.5 x10^9/L (4.0-11.0)
LAB_LINE_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9\s\-\_\/\(\)\,\.\:]+?)"  # Test name
    r"[\:\s\t]+"
    r"(?P<val>[+\-]?\d+(?:\.\d+)?)\s*"                # Numeric value
    r"(?P<unit>[A-Za-zµμ\%/\^0-9\*\-]+(?:\s*x\s*10\^\d+/[ALl])?)" # Unit
    r"(?:\s*[\(\[\{]?\s*(?P<ref>[0-9\.\-\s–to]+)\s*[\)\]\}]?)?" # Ref range
    r"\s*$",
    re.MULTILINE | re.IGNORECASE,
)

# Alternative table cell matcher for tabular rows: [TestName, Value, Unit, Range]
KNOWN_LAB_TEST_KEYWORDS = [
    "potassium", "sodium", "hemoglobin", "wbc", "white blood cell", "creatinine",
    "glucose", "platelet", "alt", "ast", "tsh", "troponin", "inr", "hba1c", "calcium",
    "bilirubin", "urea", "bun", "cholesterol", "triglycerides", "hdl", "ldl"
]


def extract_lab_values(parsed_report: ParsedReport) -> List[LabValue]:
    """
    Extract structured LabValue records from ParsedReport.

    Parameters
    ----------
    parsed_report : ParsedReport

    Returns
    -------
    List[LabValue]
    """
    extracted: List[LabValue] = []

    # 1. Rule/Regex Extraction from Tables first
    if parsed_report.tables:
        for t_idx, table in enumerate(parsed_report.tables):
            for r_idx, row in enumerate(table):
                lab_val = _try_extract_from_row(row, page_or_table=t_idx + 1, row_num=r_idx + 1)
                if lab_val:
                    extracted.append(lab_val)

    # 2. Rule/Regex Extraction from Text Blocks if tables didn't yield enough
    if not extracted and parsed_report.raw_text:
        lines = parsed_report.raw_text.splitlines()
        for l_idx, line in enumerate(lines, start=1):
            lab_val = _try_extract_from_line(line, line_num=l_idx)
            if lab_val:
                extracted.append(lab_val)

    # 3. Fallback to LLM Singleton for unstructured / messy reports if rules yielded 0
    if not extracted and parsed_report.raw_text.strip():
        logger.info("Rule extraction yielded 0 lab values. Calling LLM singleton fallback.")
        llm_extracted = _extract_via_llm_fallback(parsed_report.raw_text[:2000])
        extracted.extend(llm_extracted)

    logger.info("Stage B Extractor: Extracted %d lab values from report (format=%s)", len(extracted), parsed_report.format)
    return extracted


def _try_extract_from_row(row: List[str], page_or_table: int, row_num: int) -> Optional[LabValue]:
    """Extract LabValue from a clean table row: [Test Name, Value, Unit, Reference Range]."""
    if len(row) < 2:
        return None

    # Filter out header rows
    row_str = " ".join(row).lower()
    if "test name" in row_str or "reference range" in row_str or "result" in row_str and "unit" in row_str:
        return None

    # Try identifying columns
    test_name_raw = row[0].strip()
    if not test_name_raw or len(test_name_raw) < 2:
        return None

    value_raw_str = ""
    unit_raw = ""
    ref_range_raw = ""

    # Search for numeric value in remaining cells
    for cell_idx, cell in enumerate(row[1:], start=1):
        cell_clean = cell.strip()
        num_match = re.search(r"^[+\-]?\d+(?:\.\d+)?$", cell_clean)
        if num_match and not value_raw_str:
            value_raw_str = cell_clean
            # Check if next cell is unit
            if cell_idx + 1 < len(row):
                unit_raw = row[cell_idx + 1].strip()
            if cell_idx + 2 < len(row):
                ref_range_raw = row[cell_idx + 2].strip()
            break

    if not value_raw_str:
        return None

    try:
        val_float = float(value_raw_str)
    except ValueError:
        return None

    return LabValue(
        raw_text=" | ".join(row),
        test_name_raw=test_name_raw,
        value_raw=val_float,
        value_raw_str=value_raw_str,
        unit_raw=unit_raw,
        reference_range_raw=ref_range_raw,
        patient_context={},
        source_page=page_or_table,
        source_row=row_num,
        extraction_confidence=1.0,
        needs_review=False,
    )


def _try_extract_from_line(line: str, line_num: int) -> Optional[LabValue]:
    """Extract LabValue from a single text line using regex."""
    if not line.strip():
        return None

    match = LAB_LINE_RE.match(line)
    if not match:
        return None

    gd = match.groupdict()
    test_name_raw = gd["name"].strip()
    val_str = gd["val"].strip()
    unit_raw = gd["unit"].strip()
    ref_range_raw = (gd.get("ref") or "").strip()

    try:
        val_float = float(val_str)
    except ValueError:
        return None

    return LabValue(
        raw_text=line.strip(),
        test_name_raw=test_name_raw,
        value_raw=val_float,
        value_raw_str=val_str,
        unit_raw=unit_raw,
        reference_range_raw=ref_range_raw,
        patient_context={},
        source_page=1,
        source_row=line_num,
        extraction_confidence=1.0,
        needs_review=False,
    )


def _extract_via_llm_fallback(text_snippet: str) -> List[LabValue]:
    """Fallback LLM extraction using existing Qwen2.5-7B singleton."""
    prompt = f"""[SYSTEM] You are an exact medical laboratory report parser.
Extract all laboratory test results from the text below as a JSON list.
For every test, return:
- "test_name_raw": exact test name string
- "value_raw_str": exact byte-identical string of the numeric value
- "unit_raw": exact unit string
- "reference_range_raw": reference range string or empty string

Rules:
1. NEVER round, alter, or guess numbers.
2. Return ONLY valid JSON in format: [{{"test_name_raw": "...", "value_raw_str": "...", "unit_raw": "...", "reference_range_raw": "..."}}]

[TEXT]
{text_snippet}

[JSON OUTPUT]
"""
    try:
        llm = get_llm()
        output = llm(prompt, max_tokens=512, temperature=0.0)
        resp_text = output["choices"][0]["text"]

        # Parse JSON
        json_match = re.search(r"\[.*\]", resp_text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            res = []
            for item in data:
                val_str = str(item.get("value_raw_str", "")).strip()
                try:
                    val_float = float(val_str)
                    res.append(
                        LabValue(
                            raw_text=f"{item.get('test_name_raw')}: {val_str} {item.get('unit_raw')}",
                            test_name_raw=str(item.get("test_name_raw", "")),
                            value_raw=val_float,
                            value_raw_str=val_str,
                            unit_raw=str(item.get("unit_raw", "")),
                            reference_range_raw=str(item.get("reference_range_raw", "")),
                            extraction_confidence=0.85,
                            needs_review=False,
                        )
                    )
                except ValueError:
                    continue
            return res
    except Exception as e:
        logger.error("LLM fallback extraction failed: %s", e)

    return []
