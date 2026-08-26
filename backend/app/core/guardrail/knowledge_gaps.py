"""
MedGraphRAG Backend — Epistemic Knowledge-Gap Mapper (F2)
=========================================================
Pure, rule-based deterministic mapper that analyzes the root causes of epistemic
uncertainty (refusals, low retrieval confidence, graph path absence, or
unfaithful generation).

Core Principles:
  1. DETERMINISTIC & ZERO-LLM: Classified purely from pipeline metrics (fused_score, graph_checks, phi).
  2. ACTIONABLE CLINICAL GUIDANCE: Formulates targeted query synonyms and authoritative source recommendations.
  3. FAIL-OPEN: Returns empty list on any runtime error.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set

from app.config import settings
from app.core.guardrail.schemas import KnowledgeGap

logger = logging.getLogger(__name__)

# ── Medical Ontology Synonyms & Broader MeSH Terms ───────────────────────────
ONTOLOGY_SYNONYMS: Dict[str, List[str]] = {
    "warfarin": ["Coumadin", "vitamin K antagonist", "oral anticoagulation", "INR monitoring"],
    "inr": ["international normalized ratio", "prothrombin time", "PT/INR"],
    "atrial fibrillation": ["AFib", "supraventricular arrhythmia", "cardiac arrhythmia", "CHA2DS2-VASc"],
    "hypertension": ["high blood pressure", "essential hypertension", "antihypertensive therapy", "JNC-8 guidelines"],
    "ace inhibitor": ["angiotensin-converting enzyme inhibitor", "lisinopril", "enalapril", "RAAS blockade"],
    "hyperkalemia": ["elevated potassium", "high serum potassium", "potassium > 5.0 mEq/L", "ECG peaked T waves"],
    "hypokalemia": ["low potassium", "serum potassium < 3.5 mEq/L", "U waves"],
    "myocardial infarction": ["acute coronary syndrome", "STEMI", "NSTEMI", "cardiac ischemia", "troponin elevation"],
    "troponin": ["cardiac troponin I", "cardiac troponin T", "hs-cTn", "myocardial necrosis marker"],
    "metformin": ["Glucophage", "biguanide", "oral antihyperglycemic", "eGFR contraindication"],
    "diabetes": ["type 2 diabetes mellitus", "hyperglycemia", "HbA1c target", "ADA Standards of Care"],
    "renal failure": ["chronic kidney disease", "acute kidney injury", "decreased eGFR", "elevated creatinine", "nephropathy"],
    "creatinine": ["serum creatinine", "eGFR calculation", "renal function panel"],
    "anemia": ["low hemoglobin", "iron deficiency anemia", "microcytic anemia", "transfusion threshold"],
    "pneumothorax": ["pleural air", "tension pneumothorax", "apical pneumothorax", "chest tube decompression"],
    "pleural effusion": ["pleural fluid", "exudative effusion", "transudative effusion", "thoracentesis"],
    "pneumonia": ["community-acquired pneumonia", "pulmonary infiltrate", "bacterial pneumonia", "CURB-65"],
}


def _extract_matched_concepts(text: str) -> List[Tuple[str, List[str]]]:
    """Find recognized medical concepts and their synonyms in text."""
    text_lower = text.lower()
    matched = []
    for concept, syns in ONTOLOGY_SYNONYMS.items():
        if re.search(rf"\b{re.escape(concept)}\b", text_lower):
            matched.append((concept, syns))
    return matched


def map_knowledge_gaps(
    query: str,
    retrieved_items: Optional[List[Any]] = None,
    graph_checks: Optional[Any] = None,
    phi: Optional[float] = None,
    answer_status: Optional[str] = None,
) -> List[KnowledgeGap]:
    """
    Classify epistemic gaps and produce actionable query reformulations and source suggestions.

    Parameters
    ----------
    query : str
        The clinical question asked by the user.
    retrieved_items : list, optional
        List of EvidenceItem or dicts returned from hybrid retrieval.
    graph_checks : dict or list, optional
        Graph consistency verification checks or verdict dicts.
    phi : float, optional
        Faithfulness score (0.0 to 1.0) from verification agent.
    answer_status : str, optional
        Status of the generated answer ('verified', 'uncertain', 'refusal', 'out_of_scope', etc.).

    Returns
    -------
    List[KnowledgeGap]
        Identified epistemic gap records.
    """
    if not getattr(settings, "enable_knowledge_gap_mapper", True):
        return []

    gaps: List[KnowledgeGap] = []
    retrieved_items = retrieved_items or []

    try:
        # Normalize top fused score and top source
        top_score = 0.0
        top_source = "clinical_guidelines"
        if retrieved_items:
            first = retrieved_items[0]
            if hasattr(first, "fused_score"):
                top_score = float(first.fused_score or 0.0)
                top_source = getattr(first, "document_id", getattr(first, "chunk_id", "corpus"))
            elif isinstance(first, dict):
                top_score = float(first.get("fused_score", 0.0))
                top_source = first.get("document_id") or first.get("chunk_id") or "corpus"

        concepts = _extract_matched_concepts(query)
        primary_concept = concepts[0][0] if concepts else query[:40].strip()
        synonyms = concepts[0][1] if concepts else []

        # ── G1: Corpus Retrieval Gap (fused_score < 0.02 or empty retrieval) ──────────
        is_retrieval_gap = (top_score < 0.02 or len(retrieved_items) == 0)
        if is_retrieval_gap:
            suggested_q = []
            if synonyms:
                suggested_q.append(f"{synonyms[0]} clinical management and diagnostic guidelines")
                if len(synonyms) > 1:
                    suggested_q.append(f"{synonyms[1]} evidence summary")
            else:
                suggested_q.append(f"clinical diagnosis and therapy for {primary_concept}")
                suggested_q.append(f"guidelines regarding {primary_concept}")

            gaps.append(
                KnowledgeGap(
                    claim_text=query,
                    gap_type="corpus_retrieval",
                    detail=(
                        f"Top fused retrieval score ({top_score:.4f}) is below relevance threshold (0.02). "
                        f"The indexed corpus lacks high-density textual evidence for '{primary_concept}'."
                    ),
                    suggested_queries=suggested_q[:3],
                    suggested_sources=[
                        "PubMed Central Clinical Practice Guidelines",
                        "UpToDate / DynaMed Evidence Summaries",
                        "Cochrane Systematic Reviews",
                    ],
                )
            )

        # ── G2: Graph Coverage Gap (neutral graph check or missing direct relation) ───
        is_graph_gap = False
        graph_detail = ""
        if graph_checks:
            if isinstance(graph_checks, dict):
                v = graph_checks.get("verdict", "")
                r = graph_checks.get("reason", "")
                if v == "neutral" or "no direct graph assertion" in r.lower() or "missing" in r.lower():
                    is_graph_gap = True
                    graph_detail = r
            elif isinstance(graph_checks, list):
                for gc in graph_checks:
                    if isinstance(gc, dict):
                        v = gc.get("verdict", "")
                        r = gc.get("reason", "")
                        if v == "neutral" or "no direct graph assertion" in r.lower():
                            is_graph_gap = True
                            graph_detail = r
                            break

        # If answer was refused/uncertain and graph did not provide multi-hop path
        if not is_graph_gap and answer_status in ("refusal", "uncertain") and not is_retrieval_gap:
            # Check if graph hit rate was 0
            is_graph_gap = True
            graph_detail = f"Knowledge graph lacks relational assertion linking '{primary_concept}' via NEGATES/TEMPORAL/INDICATES."

        if is_graph_gap:
            suggested_g_q = []
            if synonyms:
                suggested_g_q.append(f"mechanism of action and indications for {synonyms[0]}")
            else:
                suggested_g_q.append(f"relational indications for {primary_concept}")

            gaps.append(
                KnowledgeGap(
                    claim_text=query,
                    gap_type="graph_coverage",
                    detail=(
                        graph_detail or f"Graph lacks explicit relational assertion linking '{primary_concept}' to clinical outcomes."
                    ),
                    suggested_queries=suggested_g_q,
                    suggested_sources=[
                        "UMLS Metathesaurus Semantic Network",
                        "DrugBank Relational Graph",
                        "SNOMED CT Clinical Hierarchy",
                    ],
                )
            )

        # ── G3: Evidence Faithfulness Gap (phi < 0.50) ───────────────────────────────
        if phi is not None and phi < 0.50 and answer_status in ("refusal", "uncertain", "caution", "contradiction_detected"):
            gaps.append(
                KnowledgeGap(
                    claim_text=query,
                    gap_type="evidence_faithfulness",
                    detail=(
                        f"Retrieved evidence faithfulness score (φ = {phi:.2f} < 0.50) indicates pipeline claims "
                        f"are unsupported or contradict the retrieved text."
                    ),
                    suggested_queries=[
                        f"consult primary source document '{top_source}' directly",
                        f"verify '{primary_concept}' with authoritative specialty consensus",
                    ],
                    suggested_sources=[f"Direct review of source: {top_source}"],
                )
            )

    except Exception as exc:
        logger.warning("Knowledge-gap mapper fail-open: caught unexpected exception: %s", exc)
        return []

    return gaps
