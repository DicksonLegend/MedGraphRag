"""
MedGraphRAG Backend — Relation-Aware Reranker (Step J3)
=========================================================
Reranks top fused evidence candidates based on typed knowledge graph relations.

Algorithm:
  1. Extract query-seeded entities from query string.
  2. For each candidate chunk c in top candidates, compute:
     rel_bonus(c) = weighted count of typed edges connecting c's document/chunk
                    to query-seeded entities.
     Edge weights:
       - DRUG_TREATS: 1.0
       - DRUG_CAUSES / DRUG_CAUSES_SE: 1.0
       - LABTEST_RELATED_TO: 0.8
       - NEGATES: 0.8
       - TEMPORAL_BEFORE: 0.6
       - IS_A / RELATED_TO: 0.3
  3. Scoring based on rerank_mode:
     - 'rrf'    : score = fused_score (pure RRF, control mode)
     - 'rel'    : score = rel_bonus   (pure relational bonus)
     - 'hybrid' : score = fused_score + gamma * rel_bonus (default gamma = 0.15)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

import kuzu

from app.config import settings
from app.core.retrieval.graph_store import get_kuzu_connection

logger = logging.getLogger(__name__)

EDGE_WEIGHTS = {
    "DRUG_TREATS": 1.0,
    "DRUG_CAUSES": 1.0,
    "DRUG_CAUSES_SE": 1.0,
    "LABTEST_RELATED_TO": 0.8,
    "NEGATES": 0.8,
    "TEMPORAL_BEFORE": 0.6,
    "IS_A": 0.3,
    "RELATED_TO": 0.3,
}

STOPWORDS = {
    "of", "in", "to", "for", "with", "on", "at", "from", "by", "an", "a", "the",
    "and", "or", "is", "are", "be", "was", "were", "what", "which", "how", "does",
    "do", "did", "mean", "meaning", "meanings", "about", "write", "me", "treatment",
    "first", "line", "risk", "side", "effects", "criteria", "changes", "diagnosis",
    "score", "mechanism", "action", "output", "rate", "levels", "threshold",
    "elevation", "failure", "organ", "dysfunction", "critical", "care", "management",
    "contraindications", "contraindication", "contraindicated", "patient", "presents"
}

SYNONYMS = {
    "warfarin": ["warfarin", "coumadin", "inr", "anticoagulation"],
    "inr": ["international normalized ratio", "warfarin", "prothrombin"],
    "afib": ["atrial fibrillation", "arrhythmia"],
    "metformin": ["metformin", "glucophage", "biguanide"],
    "diabetes": ["diabetes mellitus", "type 2 diabetes", "t2d"],
    "renal": ["kidney failure", "renal failure", "nephropathy", "chronic kidney disease"],
}


def extract_query_entities(query: str, conn: Optional[kuzu.Connection]) -> Dict[str, Set[str]]:
    """
    Extracts query-seeded entity IDs and names from Kùzu.
    Returns dict: {'Disease': {ids}, 'Drug': {ids}, 'LabTest': {ids}, 'OntologyTerm': {ids}}
    """
    entities: Dict[str, Set[str]] = {
        "Disease": set(),
        "Drug": set(),
        "LabTest": set(),
        "OntologyTerm": set(),
    }
    if conn is None:
        return entities

    raw_words = [w.lower() for w in re.findall(r"\b[a-zA-Z0-9\-]{3,}\b", query) if w.lower() not in STOPWORDS]
    bigrams = [" ".join(raw_words[i:i+2]) for i in range(len(raw_words)-1)]

    expanded: List[str] = []
    for w in raw_words:
        expanded.append(w)
        if w in SYNONYMS:
            expanded.extend(SYNONYMS[w])

    candidates = list(dict.fromkeys(bigrams + expanded))

    for term in candidates[:8]:
        if len(term) < 3:
            continue
        term_l = term.lower()

        # Query Disease
        try:
            df_d = conn.execute(
                "MATCH (d:Disease) WHERE lower(d.name) CONTAINS $t RETURN d.disease_id AS id LIMIT 3",
                {"t": term_l}
            ).get_as_df()
            for _, r in df_d.iterrows():
                entities["Disease"].add(str(r["id"]))
        except Exception:
            pass

        # Query Drug
        try:
            df_dr = conn.execute(
                "MATCH (d:Drug) WHERE lower(d.name) CONTAINS $t RETURN d.node_id AS id LIMIT 3",
                {"t": term_l}
            ).get_as_df()
            for _, r in df_dr.iterrows():
                entities["Drug"].add(str(r["id"]))
        except Exception:
            pass

        # Query LabTest
        try:
            df_lt = conn.execute(
                "MATCH (l:LabTest) WHERE lower(l.test_name) CONTAINS $t RETURN l.lab_test_id AS id LIMIT 3",
                {"t": term_l}
            ).get_as_df()
            for _, r in df_lt.iterrows():
                entities["LabTest"].add(str(r["id"]))
        except Exception:
            pass

        # Query OntologyTerm
        try:
            df_o = conn.execute(
                "MATCH (o:OntologyTerm) WHERE lower(o.term) CONTAINS $t RETURN o.term_id AS id LIMIT 3",
                {"t": term_l}
            ).get_as_df()
            for _, r in df_o.iterrows():
                entities["OntologyTerm"].add(str(r["id"]))
        except Exception:
            pass

    return entities


def compute_rel_bonus(
    item: Dict[str, Any],
    query_entities: Dict[str, Set[str]],
    conn: Optional[kuzu.Connection],
) -> float:
    """
    Compute relational bonus for a candidate chunk based on typed edges connecting
    its parent document or chunk to query-seeded entities.
    """
    if conn is None:
        return 0.0

    doc_id = str(item.get("document_id", "") or item.get("source_doc", "")).replace("'", "\\'")
    chunk_id = str(item.get("chunk_id", "")).replace("'", "\\'")

    rel_bonus = 0.0

    # 1. Check Chunk-level NEGATES edges
    try:
        q_neg = f"MATCH (c:Chunk {{chunk_id: '{chunk_id}'}})-[r:NEGATES]->(e) RETURN count(r) AS cnt"
        c_neg = conn.execute(q_neg).get_as_df().iloc[0, 0]
        if c_neg > 0:
            rel_bonus += EDGE_WEIGHTS["NEGATES"] * min(2, c_neg)
    except Exception:
        pass

    # 2. Check Chunk-level TEMPORAL_BEFORE edges
    try:
        q_temp = f"MATCH (c:Chunk {{chunk_id: '{chunk_id}'}})-[r:TEMPORAL_BEFORE]->(c2) RETURN count(r) AS cnt"
        c_temp = conn.execute(q_temp).get_as_df().iloc[0, 0]
        if c_temp > 0:
            rel_bonus += EDGE_WEIGHTS["TEMPORAL_BEFORE"] * min(2, c_temp)
    except Exception:
        pass

    # 3. Check Document-level MENTIONS & Typed Edges
    if doc_id:
        # Check if Document mentions any Drug that treats/causes a query-seeded Disease
        disease_ids = query_entities.get("Disease", set())
        drug_ids = query_entities.get("Drug", set())

        if disease_ids:
            dis_list_cypher = "[" + ", ".join(f"'{did}'" for did in list(disease_ids)[:5]) + "]"
            try:
                q_treats = f"""
                MATCH (doc:Document {{document_id: '{doc_id}'}})-[:DOCUMENT_MENTIONS]->(dr:Drug)-[r:DRUG_TREATS]->(dis:Disease)
                WHERE dis.disease_id IN {dis_list_cypher}
                RETURN count(r) AS cnt
                """
                c_tr = conn.execute(q_treats).get_as_df().iloc[0, 0]
                if c_tr > 0:
                    rel_bonus += EDGE_WEIGHTS["DRUG_TREATS"] * min(2, c_tr)
            except Exception:
                pass

            try:
                q_causes = f"""
                MATCH (doc:Document {{document_id: '{doc_id}'}})-[:DOCUMENT_MENTIONS]->(dr:Drug)-[r:DRUG_CAUSES|DRUG_CAUSES_SE]->(dis:Disease)
                WHERE dis.disease_id IN {dis_list_cypher}
                RETURN count(r) AS cnt
                """
                c_ca = conn.execute(q_causes).get_as_df().iloc[0, 0]
                if c_ca > 0:
                    rel_bonus += EDGE_WEIGHTS["DRUG_CAUSES"] * min(2, c_ca)
            except Exception:
                pass

            try:
                q_lab = f"""
                MATCH (doc:Document {{document_id: '{doc_id}'}})-[:DOCUMENT_MENTIONS]->(lt:LabTest)-[r:LABTEST_RELATED_TO]->(dis:Disease)
                WHERE dis.disease_id IN {dis_list_cypher}
                RETURN count(r) AS cnt
                """
                c_lt = conn.execute(q_lab).get_as_df().iloc[0, 0]
                if c_lt > 0:
                    rel_bonus += EDGE_WEIGHTS["LABTEST_RELATED_TO"] * min(2, c_lt)
            except Exception:
                pass

        if drug_ids:
            drug_list_cypher = "[" + ", ".join(f"'{did}'" for did in list(drug_ids)[:5]) + "]"
            try:
                q_dr_dis = f"""
                MATCH (doc:Document {{document_id: '{doc_id}'}})-[:DOCUMENT_MENTIONS]->(dis:Disease)<-[r:DRUG_TREATS]-(dr:Drug)
                WHERE dr.node_id IN {drug_list_cypher}
                RETURN count(r) AS cnt
                """
                c_dr_dis = conn.execute(q_dr_dis).get_as_df().iloc[0, 0]
                if c_dr_dis > 0:
                    rel_bonus += EDGE_WEIGHTS["DRUG_TREATS"] * min(2, c_dr_dis)
            except Exception:
                pass

    # Cap rel_bonus to prevent runaway scores
    return round(min(3.0, rel_bonus), 4)


def rerank_candidates(
    candidates: List[Dict[str, Any]],
    query: str,
    rerank_mode: Optional[str] = None,
    gamma: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Rerank fused candidates based on relation-aware knowledge graph bonus.

    Parameters
    ----------
    candidates : List[Dict[str, Any]]
        Candidate items from RRF fusion.
    query : str
        The query string.
    rerank_mode : str
        'rrf' (default, control), 'rel' (relational-only), 'hybrid'.
    gamma : float
        Weight for relational bonus in hybrid mode (default 0.15).

    Returns
    -------
    List of candidates re-sorted according to the requested rerank_mode.
    """
    mode = (rerank_mode or getattr(settings, "retrieval_rerank_mode", "rrf")).lower()
    g = gamma if gamma is not None else getattr(settings, "retrieval_rerank_gamma", 0.15)

    if mode == "rrf" or not candidates:
        # Pure RRF baseline — return unmodified
        for item in candidates:
            item["rel_bonus"] = 0.0
            item["rerank_score"] = item["fused_score"]
        return candidates

    conn = get_kuzu_connection()
    query_entities = extract_query_entities(query, conn)

    # Compute rel_bonus for top-20 candidates
    for item in candidates[:20]:
        rb = compute_rel_bonus(item, query_entities, conn)
        item["rel_bonus"] = rb
        if mode == "rel":
            item["rerank_score"] = rb
        elif mode == "hybrid":
            item["rerank_score"] = round(item["fused_score"] + (g * rb), 6)
        else:
            item["rerank_score"] = item["fused_score"]

    for item in candidates[20:]:
        item["rel_bonus"] = 0.0
        item["rerank_score"] = item["fused_score"]

    # Re-sort candidates by rerank_score descending
    reranked = sorted(candidates, key=lambda x: (x.get("rerank_score", 0.0), x.get("fused_score", 0.0)), reverse=True)
    return reranked
