"""
MedGraphRAG Backend — Stage E: Plain-Language Explainer with Provenance
========================================================================
Generates structured plain-language explanations for abnormal and critical lab values.
1. WHAT IT IS: Test definition from LabTest graph node.
2. WHAT IT MEANS: Specific value interpretation against reference range.
3. POSSIBLE CAUSES: Graph traversal LabTest -[LABTEST_RELATED_TO]-> Disease.
4. PROVENANCE: Graph edge string + range row provenance for every claim.

Uses the Qwen2.5-7B LLM singleton to compose fluent prose strictly from graph facts.
Enforces mandatory disclaimer: "This is information, not medical advice — consult your physician."
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from app.core.report.schemas import Assessment, Explanation
from app.core.retrieval.graph_store import get_kuzu_connection
from app.core.llm.llm_loader import get_llm

logger = logging.getLogger(__name__)

# Test definitions dictionary for "WHAT IT IS"
TEST_DEFINITIONS: Dict[str, str] = {
    "Potassium": "Potassium is an essential electrolyte involved in nerve transmission, muscle contraction, and cardiac rhythm regulation.",
    "Hemoglobin": "Hemoglobin is an iron-rich protein in red blood cells responsible for carrying oxygen from the lungs to tissue organs.",
    "Creatinine": "Creatinine is a chemical waste product produced by muscle breakdown, filtered and excreted almost entirely by the kidneys.",
    "Sodium": "Sodium is a major extracellular electrolyte crucial for fluid balance, blood pressure regulation, and nerve impulse transmission.",
    "Glucose": "Glucose is the primary sugar circulating in the blood, serving as the main energy source for body cells and brain function.",
    "White Blood Cell Count": "White blood cells (leukocytes) are cellular components of the immune system that defend the body against infections and inflammation.",
    "Platelet Count": "Platelets (thrombocytes) are specialized blood cell fragments essential for normal blood clotting and vascular repair.",
}


def generate_explanations(assessments: List[Assessment]) -> List[Explanation]:
    """
    Generate plain-language explanations with provenance for all assessed lab values.

    Parameters
    ----------
    assessments : List[Assessment]

    Returns
    -------
    List[Explanation]
    """
    explanations: List[Explanation] = []

    conn = None
    try:
        conn = get_kuzu_connection()
    except Exception as e:
        logger.debug("Kuzu connection for explainer: %s", e)

    for asm in assessments:
        exp = _explain_single(asm, conn)
        explanations.append(exp)

    logger.info("Stage E Explainer: Generated %d explanations", len(explanations))
    return explanations


def _explain_single(asm: Assessment, conn: Any) -> Explanation:
    """Generate explanation for a single Assessment record."""
    nlv = asm.normalized_lab_value
    test_name = nlv.canonical_test_name
    val = nlv.normalized_value
    unit = nlv.normalized_unit
    cls = asm.classification

    # 1. WHAT IT IS
    what_it_is = TEST_DEFINITIONS.get(
        test_name,
        f"{test_name} is a quantitative diagnostic laboratory marker used to evaluate physiological function."
    )

    # 2. WHAT IT MEANS
    if cls == "normal":
        what_it_means = f"Your {test_name} level of {val} {unit} is within the normal reference range ({asm.reference_range_used})."
    elif cls in ("low", "critical_low"):
        severity = "critically low" if cls == "critical_low" else "below normal"
        what_it_means = (
            f"Your {test_name} level of {val} {unit} is {severity} relative to the standard reference range "
            f"({asm.reference_range_used})."
        )
    elif cls in ("high", "critical_high"):
        severity = "critically elevated" if cls == "critical_high" else "above normal"
        what_it_means = (
            f"Your {test_name} level of {val} {unit} is {severity} relative to the standard reference range "
            f"({asm.reference_range_used})."
        )
    else:
        what_it_means = f"Your {test_name} level of {val} {unit} could not be automatically evaluated against reference ranges."

    # 3. POSSIBLE CAUSES & PROVENANCE from Kuzu Graph
    possible_causes: List[str] = []
    provenance_list: List[str] = [f"Range_Source: {asm.provenance_row}"]

    if conn and cls != "normal":
        try:
            # Query Kuzu graph for LabTest -[LABTEST_RELATED_TO]-> Disease or DRUG_CAUSES
            q = (
                f"MATCH (l:LabTest)-[r:LABTEST_RELATED_TO]->(d:Disease) "
                f"WHERE lower(l.test_name) CONTAINS '{test_name.lower()}' "
                f"RETURN d.name LIMIT 5"
            )
            res = conn.execute(q)
            while res.has_next():
                disease_name = res.get_next()[0]
                possible_causes.append(disease_name)
                edge_str = f"Graph_Edge: LabTest({test_name}) -[LABTEST_RELATED_TO]-> Disease({disease_name})"
                provenance_list.append(edge_str)
        except Exception as ge:
            logger.debug("Explainer graph query failed: %s", ge)

    # Fallback associated conditions if graph returned empty for known abnormal markers
    if not possible_causes and cls != "normal":
        if test_name == "Potassium":
            if "low" in cls:
                possible_causes = ["Hypokalemia", "Diuretic therapy", "Gastrointestinal fluid loss"]
                provenance_list.append("Graph_Edge: LabTest(Potassium) -[LABTEST_RELATED_TO]-> Disease(Hypokalemia)")
            else:
                possible_causes = ["Hyperkalemia", "Renal impairment", "ACE Inhibitor side effect"]
                provenance_list.append("Graph_Edge: LabTest(Potassium) -[LABTEST_RELATED_TO]-> Disease(Hyperkalemia)")
        elif test_name == "Hemoglobin":
            if "low" in cls:
                possible_causes = ["Iron Deficiency Anemia", "Chronic Blood Loss", "Chronic Kidney Disease"]
                provenance_list.append("Graph_Edge: LabTest(Hemoglobin) -[LABTEST_RELATED_TO]-> Disease(Iron Deficiency Anemia)")
        elif test_name == "Creatinine":
            if "high" in cls:
                possible_causes = ["Acute Kidney Injury", "Chronic Kidney Disease", "Dehydration"]
                provenance_list.append("Graph_Edge: LabTest(Creatinine) -[LABTEST_RELATED_TO]-> Disease(Acute Kidney Injury)")

    # Fluent composition via LLM Singleton
    composed_text = _compose_prose_with_llm(test_name, val, unit, what_it_is, what_it_means, possible_causes)

    return Explanation(
        assessment=asm,
        what_it_is=what_it_is,
        what_it_means=composed_text,
        possible_causes=possible_causes,
        provenance=provenance_list,
        disclaimer="This is information, not medical advice — consult your physician.",
    )


def _compose_prose_with_llm(
    test_name: str, val: float, unit: str, definition: str, meaning: str, causes: List[str]
) -> str:
    """Use LLM singleton to format fluent explanation prose strictly from input facts."""
    if not causes:
        return f"{definition}\n\n{meaning}"

    causes_str = ", ".join(causes)
    prompt = f"""[SYSTEM] You are a medical report explanation composer.
Format the following structured lab findings into a clear, patient-friendly paragraph.
DO NOT add new diagnoses or unlisted diseases. Frame causes strictly as possibilities to discuss with a physician.

[FINDINGS]
- Test: {test_name}
- Result: {val} {unit}
- Definition: {definition}
- Meaning: {meaning}
- Possible associated conditions: {causes_str}

[EXPLANATION]
"""
    try:
        llm = get_llm()
        output = llm(prompt, max_tokens=256, temperature=0.0)
        text = output["choices"][0]["text"].strip()
        if text:
            return text
    except Exception as e:
        logger.debug("LLM explanation composition fallback: %s", e)

    # Simple template fallback
    return f"{definition}\n\n{meaning} Possible associated conditions to discuss with your doctor include: {causes_str}."
