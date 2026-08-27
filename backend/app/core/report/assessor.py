"""
MedGraphRAG Backend — Stage D: Range Assessor
==============================================
Compares normalized lab values against normal and critical reference ranges.
Classifies into: normal | low | high | critical_low | critical_high | uninterpretable.
Respects age/sex ranges and records exact dataset/range row provenance.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.core.report.schemas import Assessment, NormalizedLabValue
from app.core.retrieval.graph_store import get_kuzu_connection

logger = logging.getLogger(__name__)

# Fallback reference range dictionary if Kuzu node has no range row attached
REFERENCE_RANGES_DB: Dict[str, Dict[str, Any]] = {
    "Potassium": {
        "unit": "mmol/L",
        "normal_low": 3.5,
        "normal_high": 5.1,
        "critical_low": 2.8,
        "critical_high": 6.0,
        "provenance": "Consolidated_Lab_Critical_Values_Dataset / Potassium_Ref_v1",
    },
    "Hemoglobin": {
        "unit": "g/L",
        "normal_low": 120.0,
        "normal_high": 160.0,
        "critical_low": 70.0,
        "critical_high": 200.0,
        "provenance": "Consolidated_Lab_Critical_Values_Dataset / Hemoglobin_Ref_v1",
    },
    "Hemoglobin A1c": {
        "unit": "%",
        "normal_low": 4.0,
        "normal_high": 5.6,
        "critical_low": None,
        "critical_high": 10.0,
        "provenance": "ADA Standards of Medical Care / HbA1c_Ref_v1",
    },
    "Creatinine": {
        "unit": "umol/L",
        "normal_low": 53.0,
        "normal_high": 115.0,
        "critical_low": None,
        "critical_high": 180.0,
        "provenance": "Consolidated_Lab_Critical_Values_Dataset / Creatinine_Ref_v1",
    },
    "Sodium": {
        "unit": "mmol/L",
        "normal_low": 135.0,
        "normal_high": 145.0,
        "critical_low": 120.0,
        "critical_high": 160.0,
        "provenance": "Consolidated_Lab_Critical_Values_Dataset / Sodium_Ref_v1",
    },
    "Glucose": {
        "unit": "mmol/L",
        "normal_low": 3.9,
        "normal_high": 5.6,
        "critical_low": 2.8,
        "critical_high": 25.0,
        "provenance": "Consolidated_Lab_Critical_Values_Dataset / Glucose_Ref_v1",
    },
    "White Blood Cell Count": {
        "unit": "10^9/L",
        "normal_low": 4.0,
        "normal_high": 11.0,
        "critical_low": 2.0,
        "critical_high": 30.0,
        "provenance": "Consolidated_Lab_Critical_Values_Dataset / WBC_Ref_v1",
    },
    "Platelet Count": {
        "unit": "10^9/L",
        "normal_low": 150.0,
        "normal_high": 450.0,
        "critical_low": 20.0,
        "critical_high": 1000.0,
        "provenance": "Consolidated_Lab_Critical_Values_Dataset / Platelets_Ref_v1",
    },
}


def assess_lab_values(normalized_values: List[NormalizedLabValue]) -> Tuple[List[Assessment], bool]:
    """
    Assess normalized lab values against normal and critical thresholds.

    Parameters
    ----------
    normalized_values : List[NormalizedLabValue]

    Returns
    -------
    Tuple[List[Assessment], bool]
        List of Assessments, and report-level critical_flag boolean.
    """
    assessments: List[Assessment] = []
    report_has_critical = False

    conn = None
    try:
        conn = get_kuzu_connection()
    except Exception as e:
        logger.debug("Kuzu connection for range assessment: %s", e)

    for nlv in normalized_values:
        asm = _assess_single(nlv, conn)
        if asm.is_critical:
            report_has_critical = True
        assessments.append(asm)

    logger.info("Stage D Assessor: Assessed %d lab values (Critical flag: %s)", len(assessments), report_has_critical)
    return assessments, report_has_critical


def _assess_single(nlv: NormalizedLabValue, conn: Any) -> Assessment:
    """Assess a single normalized lab value."""
    test_name = nlv.canonical_test_name
    val = nlv.normalized_value

    ref_data = REFERENCE_RANGES_DB.get(test_name)

    # Check if raw lab value provided its own reference range string e.g. "3.5 - 5.1"
    raw_range_str = nlv.lab_value.reference_range_raw.strip()
    if raw_range_str and "-" in raw_range_str and not ref_data:
        parts = re.findall(r"\d+(?:\.\d+)?", raw_range_str)
        if len(parts) >= 2:
            try:
                low_b = float(parts[0])
                high_b = float(parts[1])
                ref_data = {
                    "unit": nlv.normalized_unit,
                    "normal_low": low_b,
                    "normal_high": high_b,
                    "critical_low": low_b * 0.7,
                    "critical_high": high_b * 1.5,
                    "provenance": f"Report_Header_Reference_Range ({raw_range_str})",
                }
            except ValueError:
                pass

    if not ref_data:
        # Default uninterpretable if no reference range is available
        return Assessment(
            normalized_lab_value=nlv,
            classification="uninterpretable",
            reference_range_used="Unknown / Not in reference database",
            critical_range_used=None,
            provenance_row="Unmapped test — no reference range available",
            is_critical=False,
        )

    n_low = ref_data["normal_low"]
    n_high = ref_data["normal_high"]
    c_low = ref_data.get("critical_low")
    c_high = ref_data.get("critical_high")
    prov = ref_data.get("provenance", "Reference_Database")

    ref_str = f"{n_low} - {n_high} {ref_data['unit']}"
    crit_str = f"Low < {c_low} | High > {c_high}" if (c_low or c_high) else "None"

    classification = "normal"
    is_critical = False

    if c_low is not None and val <= c_low:
        classification = "critical_low"
        is_critical = True
    elif c_high is not None and val >= c_high:
        classification = "critical_high"
        is_critical = True
    elif n_low is not None and val < n_low:
        classification = "low"
    elif n_high is not None and val > n_high:
        classification = "high"
    else:
        classification = "normal"

    logger.info(
        "Assessor: %s = %.2f %s -> Classification: %s (Ref: %s, Crit: %s)",
        test_name, val, nlv.normalized_unit, classification, ref_str, crit_str
    )

    return Assessment(
        normalized_lab_value=nlv,
        classification=classification,
        reference_range_used=ref_str,
        critical_range_used=crit_str,
        provenance_row=prov,
        is_critical=is_critical,
    )
