"""
MedGraphRAG Backend — Graph Consistency Checker (Step J2)
==========================================================
Second-pass verification against the Kùzu Knowledge Graph:
  1. Drug–Disease claims: Checks DRUG_TREATS, DRUG_CAUSES, DRUG_CAUSES_SE.
  2. Negation contradiction: Checks if an asserted entity has a NEGATES edge in the top retrieved evidence chunks.
  3. Temporal sequencing: Checks sequence assertions against TEMPORAL_BEFORE.

Returns:
  - graph_verifications: list of per-claim graph checks
  - graph_consistency_score S_g: (0.0 to 1.0) = consistent / checked
  - has_graph_contradiction: bool (True if any asserted claim is directly negated)
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

import kuzu

from app.config import settings
from app.core.retrieval.graph_store import get_kuzu_connection
from app.core.retrieval.schemas import RetrievalResult
from app.core.verification.schemas import Claim

logger = logging.getLogger(__name__)

WORD_RE = re.compile(r"[a-z0-9\-\+\%]+", re.IGNORECASE)

_ENTITY_MAPS_LOADED = False
_DISEASE_MAP: Dict[str, Tuple[str, str]] = {}
_DRUG_MAP: Dict[str, Tuple[str, str]] = {}
_ONTO_MAP: Dict[str, Tuple[str, str]] = {}


def _init_entity_maps(conn: kuzu.Connection) -> None:
    global _ENTITY_MAPS_LOADED, _DISEASE_MAP, _DRUG_MAP, _ONTO_MAP
    if _ENTITY_MAPS_LOADED:
        return

    try:
        res_dis = conn.execute("MATCH (d:Disease) RETURN d.disease_id, d.name, d.aliases").get_as_df()
        for did, name, aliases_j in zip(res_dis["d.disease_id"], res_dis["d.name"], res_dis["d.aliases"]):
            if name and len(name) > 2:
                _DISEASE_MAP[name.lower().strip()] = (str(did), str(name))
            try:
                for al in json.loads(aliases_j or "[]"):
                    if al and len(al) > 2:
                        _DISEASE_MAP[al.lower().strip()] = (str(did), str(name))
            except Exception:
                pass

        res_drug = conn.execute("MATCH (d:Drug) RETURN d.node_id, d.name").get_as_df()
        for nid, name in zip(res_drug["d.node_id"], res_drug["d.name"]):
            if name and len(name) > 2:
                _DRUG_MAP[name.lower().strip()] = (str(nid), str(name))

        res_onto = conn.execute("MATCH (o:OntologyTerm) RETURN o.term_id, o.term, o.aliases").get_as_df()
        for tid, term, aliases_j in zip(res_onto["o.term_id"], res_onto["o.term"], res_onto["o.aliases"]):
            if term and len(term) > 2:
                _ONTO_MAP[term.lower().strip()] = (str(tid), str(term))
            try:
                for al in json.loads(aliases_j or "[]"):
                    if al and len(al) > 2:
                        _ONTO_MAP[al.lower().strip()] = (str(tid), str(term))
            except Exception:
                pass

        _ENTITY_MAPS_LOADED = True
        logger.info(
            "Graph Consistency Checker: Loaded entity maps (%d Disease, %d Drug, %d Ontology terms)",
            len(_DISEASE_MAP), len(_DRUG_MAP), len(_ONTO_MAP),
        )
    except Exception as e:
        logger.warning("Graph Consistency Checker: Failed to load entity maps: %s", e)


def extract_claim_entities(claim_text: str) -> List[Tuple[str, str, str]]:
    """
    Extracts entities mentioned in a claim using fast n-gram hash lookups.
    Returns list of (entity_type, entity_id, canonical_name).
    """
    words = WORD_RE.findall(claim_text.lower())
    L = len(words)
    hits: List[Tuple[str, str, str]] = []
    seen: Set[str] = set()

    for n in range(min(5, L), 0, -1):
        for i in range(L - n + 1):
            ng = " ".join(words[i:i+n])
            if ng in seen or len(ng) < 3:
                continue
            if ng in _DRUG_MAP:
                nid, name = _DRUG_MAP[ng]
                hits.append(("Drug", nid, name))
                seen.add(ng)
            elif ng in _DISEASE_MAP:
                did, name = _DISEASE_MAP[ng]
                hits.append(("Disease", did, name))
                seen.add(ng)
            elif ng in _ONTO_MAP:
                oid, name = _ONTO_MAP[ng]
                hits.append(("OntologyTerm", oid, name))
                seen.add(ng)
            if len(hits) >= 4:
                break
    return hits


def check_graph_consistency(
    claims: List[Claim],
    retrieval_result: Optional[RetrievalResult] = None,
) -> Tuple[List[Dict[str, Any]], float, bool]:
    """
    Verify claims against the Kùzu graph.

    Returns:
      - graph_verifications: list of per-claim verification dicts
      - graph_consistency_score S_g: float (0.0 to 1.0)
      - has_graph_contradiction: bool
    """
    conn = get_kuzu_connection()
    if conn is None:
        return [], 1.0, False

    _init_entity_maps(conn)

    # 1. Fetch negated entities from the top retrieved chunks
    retrieved_chunk_ids = []
    if retrieval_result and retrieval_result.items:
        retrieved_chunk_ids = [item.chunk_id for item in retrieval_result.items[:8]]

    negated_targets: Dict[str, Dict[str, Any]] = {}
    if retrieved_chunk_ids:
        try:
            # Query NEGATES edges for retrieved chunks
            # Construct parameterized / IN query
            chunk_list_cypher = "[" + ", ".join(f"'{cid}'" for cid in retrieved_chunk_ids) + "]"
            
            q_neg_dis = f"MATCH (c:Chunk)-[r:NEGATES]->(d:Disease) WHERE c.chunk_id IN {chunk_list_cypher} RETURN c.chunk_id AS chunk_id, d.disease_id AS target_id, d.name AS name, r.cue AS cue, r.scope_text AS scope"
            df_nd = conn.execute(q_neg_dis).get_as_df()
            for _, row in df_nd.iterrows():
                negated_targets[str(row["target_id"]).lower()] = {
                    "name": str(row["name"]).lower(),
                    "chunk_id": str(row["chunk_id"]),
                    "cue": str(row["cue"]),
                    "scope": str(row["scope"]),
                }
                negated_targets[str(row["name"]).lower()] = negated_targets[str(row["target_id"]).lower()]

            q_neg_ont = f"MATCH (c:Chunk)-[r:NEGATES]->(o:OntologyTerm) WHERE c.chunk_id IN {chunk_list_cypher} RETURN c.chunk_id AS chunk_id, o.term_id AS target_id, o.term AS name, r.cue AS cue, r.scope_text AS scope"
            df_no = conn.execute(q_neg_ont).get_as_df()
            for _, row in df_no.iterrows():
                negated_targets[str(row["target_id"]).lower()] = {
                    "name": str(row["name"]).lower(),
                    "chunk_id": str(row["chunk_id"]),
                    "cue": str(row["cue"]),
                    "scope": str(row["scope"]),
                }
                negated_targets[str(row["name"]).lower()] = negated_targets[str(row["target_id"]).lower()]

            q_neg_drg = f"MATCH (c:Chunk)-[r:NEGATES]->(d:Drug) WHERE c.chunk_id IN {chunk_list_cypher} RETURN c.chunk_id AS chunk_id, d.node_id AS target_id, d.name AS name, r.cue AS cue, r.scope_text AS scope"
            df_ng = conn.execute(q_neg_drg).get_as_df()
            for _, row in df_ng.iterrows():
                negated_targets[str(row["target_id"]).lower()] = {
                    "name": str(row["name"]).lower(),
                    "chunk_id": str(row["chunk_id"]),
                    "cue": str(row["cue"]),
                    "scope": str(row["scope"]),
                }
                negated_targets[str(row["name"]).lower()] = negated_targets[str(row["target_id"]).lower()]
        except Exception as e:
            logger.debug("Graph Consistency: NEGATES lookup note: %s", e)

    graph_verifications: List[Dict[str, Any]] = []
    checked_count = 0
    consistent_count = 0
    has_graph_contradiction = False

    for claim in claims:
        text = claim.claim_text
        text_lower = text.lower()
        entities = extract_claim_entities(text)

        claim_checked = False
        verdict = "neutral"
        reason = "No direct graph assertion found."
        negating_chunk = None
        negating_cue = None

        # A. Check for Negation Contradictions (asserting present an entity that retrieved chunk negates)
        # If the claim is affirmative (does not explicitly contain negation itself)
        is_claim_negative = any(neg in text_lower for neg in ["no ", "not ", "denies", "without", "ruled out", "negative"])
        
        for etype, eid, ename in entities:
            e_key = eid.lower()
            name_key = ename.lower()
            if (e_key in negated_targets or name_key in negated_targets) and not is_claim_negative:
                # Direct Contradiction!
                neg_info = negated_targets.get(e_key) or negated_targets.get(name_key)
                verdict = "contradicted_by_graph_negation"
                claim_checked = True
                has_graph_contradiction = True
                negating_chunk = neg_info["chunk_id"]
                negating_cue = neg_info["cue"]
                reason = f"Entity '{ename}' asserted present, but retrieved chunk '{neg_info['chunk_id']}' explicitly negates it (cue: '{neg_info['cue']}')."
                break

        # B. Check Drug-Disease assertions (DRUG_TREATS, DRUG_CAUSES, DRUG_CAUSES_SE)
        if not claim_checked and len(entities) >= 2:
            drugs = [e for e in entities if e[0] == "Drug"]
            diseases = [e for e in entities if e[0] == "Disease"]

            if drugs and diseases:
                d_id = drugs[0][1]
                dis_id = diseases[0][1]
                try:
                    q_treats = f"MATCH (d:Drug {{node_id: '{d_id}'}})-[r:DRUG_TREATS]->(dis:Disease {{disease_id: '{dis_id}'}}) RETURN count(r) AS c"
                    cnt_t = conn.execute(q_treats).get_as_df().iloc[0, 0]
                    if cnt_t > 0:
                        verdict = "consistent_drug_treats"
                        claim_checked = True
                        consistent_count += 1
                        reason = f"Graph confirms Drug '{drugs[0][2]}' treats Disease '{diseases[0][2]}'."
                    else:
                        q_causes = f"MATCH (d:Drug {{node_id: '{d_id}'}})-[r:DRUG_CAUSES|DRUG_CAUSES_SE]->(dis:Disease {{disease_id: '{dis_id}'}}) RETURN count(r) AS c"
                        cnt_c = conn.execute(q_causes).get_as_df().iloc[0, 0]
                        if cnt_c > 0:
                            verdict = "consistent_drug_causes"
                            claim_checked = True
                            consistent_count += 1
                            reason = f"Graph confirms Drug '{drugs[0][2]}' causes Disease/SE '{diseases[0][2]}'."
                except Exception as e:
                    logger.debug("Graph Consistency: Drug-disease lookup note: %s", e)

        # C. Check Temporal Precedence (TEMPORAL_BEFORE)
        if not claim_checked and len(entities) >= 2:
            if any(t_word in text_lower for t_word in ["before", "prior to", "first-line", "followed by", "after"]):
                e1, e2 = entities[0], entities[1]
                if e1[0] == e2[0] and e1[1] != e2[1]:
                    try:
                        table = e1[0]  # 'Drug' or 'Disease'
                        pk_col = "node_id" if table == "Drug" else "disease_id"
                        q_temp = f"MATCH (a:{table} {{{pk_col}: '{e1[1]}'}})-[r:TEMPORAL_BEFORE]->(b:{table} {{{pk_col}: '{e2[1]}'}}) RETURN count(r) AS c"
                        cnt_tb = conn.execute(q_temp).get_as_df().iloc[0, 0]
                        if cnt_tb > 0:
                            verdict = "consistent_temporal_before"
                            claim_checked = True
                            consistent_count += 1
                            reason = f"Graph confirms '{e1[2]}' precedes '{e2[2]}'."
                    except Exception as e:
                        logger.debug("Graph Consistency: Temporal lookup note: %s", e)

        if claim_checked:
            checked_count += 1
            if verdict.startswith("consistent"):
                pass  # already incremented consistent_count
        else:
            # Default consistent if no graph edge contradicts
            consistent_count += 1
            checked_count += 1

        graph_verifications.append({
            "claim_text": text,
            "verdict": verdict,
            "reason": reason,
            "negating_chunk": negating_chunk,
            "negating_cue": negating_cue,
        })

    s_g = round(consistent_count / max(1, checked_count), 4) if checked_count > 0 else 1.0
    return graph_verifications, s_g, has_graph_contradiction
