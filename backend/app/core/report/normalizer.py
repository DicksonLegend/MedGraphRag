"""
MedGraphRAG Backend — Stage C: Normalizer & Ontology Mapper
============================================================
Maps raw test names to canonical LabTest nodes / LOINC codes in the Kùzu graph.
Normalizes units with explicit logged conversion factors.
Preserves original values and units alongside normalized versions.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple

from app.config import settings
from app.core.report.schemas import LabValue, NormalizedLabValue
from app.core.retrieval.graph_store import get_kuzu_connection

logger = logging.getLogger(__name__)

# Canonical lab test aliases mapping dictionary
CANONICAL_ALIASES: Dict[str, Tuple[str, str, str]] = {
    # alias_lower: (canonical_name, loinc_code, default_target_unit)
    "potassium": ("Potassium", "2823-3", "mmol/L"),
    "k+": ("Potassium", "2823-3", "mmol/L"),
    "sodium": ("Sodium", "2951-2", "mmol/L"),
    "na+": ("Sodium", "2951-2", "mmol/L"),
    "hemoglobin": ("Hemoglobin", "718-7", "g/L"),
    "hb": ("Hemoglobin", "718-7", "g/L"),
    "hgb": ("Hemoglobin", "718-7", "g/L"),
    "creatinine": ("Creatinine", "2160-0", "umol/L"),
    "scr": ("Creatinine", "2160-0", "umol/L"),
    "wbc": ("White Blood Cell Count", "6690-2", "10^9/L"),
    "white blood cell": ("White Blood Cell Count", "6690-2", "10^9/L"),
    "white blood cell count": ("White Blood Cell Count", "6690-2", "10^9/L"),
    "glucose": ("Glucose", "2345-7", "mmol/L"),
    "fasting glucose": ("Glucose", "2345-7", "mmol/L"),
    "platelet": ("Platelet Count", "777-3", "10^9/L"),
    "platelet count": ("Platelet Count", "777-3", "10^9/L"),
    "plt": ("Platelet Count", "777-3", "10^9/L"),
    "inr": ("Prothrombin Time INR", "6301-6", ""),
    "alt": ("Alanine Aminotransferase", "1742-6", "U/L"),
    "ast": ("Aspartate Aminotransferase", "1920-8", "U/L"),
    "tsh": ("Thyroid Stimulating Hormone", "3016-3", "mIU/L"),
    "troponin": ("Troponin I", "10839-9", "ng/mL"),
}


def normalize_lab_values(lab_values: List[LabValue]) -> List[NormalizedLabValue]:
    """
    Normalize lab test names and convert units with logged proof factors.

    Parameters
    ----------
    lab_values : List[LabValue]

    Returns
    -------
    List[NormalizedLabValue]
    """
    normalized_list: List[NormalizedLabValue] = []

    conn = None
    try:
        conn = get_kuzu_connection()
    except Exception as e:
        logger.warning("Could not establish Kuzu connection for lab normalization: %s", e)

    for lv in lab_values:
        norm_item = _normalize_single(lv, conn)
        normalized_list.append(norm_item)

    logger.info("Stage C Normalizer: Normalized %d lab values", len(normalized_list))
    return normalized_list


def _normalize_single(lv: LabValue, conn: Any) -> NormalizedLabValue:
    """Normalize a single LabValue record."""
    raw_name_lower = lv.test_name_raw.strip().lower()
    # Remove extra details in parens if present e.g. "Creatinine (KFT)" -> "creatinine"
    clean_name = re.sub(r"\(.*?\)", "", raw_name_lower).strip()

    canonical_name = lv.test_name_raw
    loinc_code = None
    target_unit = lv.unit_raw
    mapping_confidence = 0.5
    mapped = False

    # 1. Alias dictionary lookup first
    if clean_name in CANONICAL_ALIASES:
        canonical_name, loinc_code, def_unit = CANONICAL_ALIASES[clean_name]
        mapping_confidence = 1.0
        mapped = True
        if def_unit:
            target_unit = def_unit
    else:
        # Check partial match
        for alias, (c_name, l_code, def_unit) in CANONICAL_ALIASES.items():
            if alias in clean_name:
                canonical_name = c_name
                loinc_code = l_code
                mapping_confidence = 0.85
                mapped = True
                if def_unit:
                    target_unit = def_unit
                break

    # 2. Graph Lookup in Kuzu LabTest table if not found in alias dict
    if not mapped and conn:
        try:
            res = conn.execute(
                f"MATCH (l:LabTest) WHERE lower(l.test_name) CONTAINS '{clean_name[:15]}' RETURN l.test_name LIMIT 1"
            )
            if res.has_next():
                row = res.get_next()
                canonical_name = row[0]
                mapping_confidence = 0.8
                mapped = True
        except Exception as ge:
            logger.debug("Graph lookup for %s failed: %s", clean_name, ge)

    # 3. Unit Conversion
    unit_raw_clean = lv.unit_raw.strip().lower().replace(" ", "")
    target_unit_clean = target_unit.strip().lower().replace(" ", "")
    exact_key = f"{clean_name}_{unit_raw_clean}->{target_unit_clean}"

    factor = 1.0
    if exact_key in settings.unit_conversion_factors:
        factor = settings.unit_conversion_factors[exact_key]
    elif unit_raw_clean == target_unit_clean:
        factor = 1.0
    else:
        # Fallback partial check on clean test name
        for key, f_val in settings.unit_conversion_factors.items():
            if key.startswith(clean_name) and unit_raw_clean in key and target_unit_clean in key:
                factor = f_val
                break

    normalized_val = round(lv.value_raw * factor, 4)

    logger.info(
        "Normalizer: %s (%s %s) -> Canonical: %s (%s %s) [Factor: %.2f, Mapped: %s]",
        lv.test_name_raw, lv.value_raw_str, lv.unit_raw,
        canonical_name, normalized_val, target_unit or lv.unit_raw,
        factor, mapped
    )

    return NormalizedLabValue(
        lab_value=lv,
        canonical_test_name=canonical_name,
        loinc_code=loinc_code,
        normalized_value=normalized_val,
        normalized_unit=target_unit or lv.unit_raw,
        unit_conversion_factor=factor,
        mapping_confidence=mapping_confidence,
        mapped=mapped,
    )
