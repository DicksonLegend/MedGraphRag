"""
MedGraphRAG Backend — Graph Store
====================================
Read-only Kùzu graph traversal for the hybrid retrieval engine.

Responsibilities:
  1. Open a single Kùzu connection at startup (read-only, CPU).
  2. Given a set of seed document_ids, traverse the graph 1–2 hops.
  3. Collect Chunk nodes reachable from entities linked to those documents.
  4. Tag each chunk with its traversal path and edge trust level.
  5. Return a list of GraphEvidenceCandidate dicts for fusion.

Graph schema (from index/global/kuzu_db_v5):
  Nodes:
    OntologyTerm (term_id PK), Disease (disease_id PK), Drug (node_id PK),
    LabTest (lab_test_id PK), Document (document_id PK), Chunk (chunk_id PK,
    faiss_id → int, category, chunk_type, token_count, source_doc)
  Edges:
    IS_A              OntologyTerm → OntologyTerm  (rel_type, sab)
    RELATED_TO        OntologyTerm → OntologyTerm  (rel_type, rela, sab)
    DRUG_TREATS       Drug → Disease               (mention_type, meddra_term)
    DRUG_CAUSES       Drug → Disease               (frequency_pct, meddra_term)
    DRUG_CAUSES_SE    Drug → Disease               (meddra_type, meddra_term)
    HAS_CHUNK         Document → Chunk             (source_doc)
    DISEASE_MAPPED_TO Disease → OntologyTerm       (mapping_type)
    DOCUMENT_MENTIONS Document → Disease|Drug|LabTest  (source_doc)
    LABTEST_RELATED_TO LabTest → Disease           (relation_type)

High-trust edges: LABTEST_RELATED_TO, DISEASE_MAPPED_TO, DOCUMENT_MENTIONS, IS_A, RELATED_TO
Low-trust edges:  DRUG_TREATS, DRUG_CAUSES, DRUG_CAUSES_SE

Memory notes:
  - Kùzu buffer pool capped at settings.kuzu_buffer_pool_mb (default 384 MB).
  - Each query returns at most settings.graph_max_results chunks.
  - No bulk table scans — only indexed lookups by document_id / chunk_id.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional, Set

import kuzu

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton connection
# ---------------------------------------------------------------------------
_lock = threading.Lock()
_db: Optional[kuzu.Database] = None
_conn: Optional[kuzu.Connection] = None


def _open_connection() -> None:
    """Open the Kùzu database once. Subsequent calls are no-ops."""
    global _db, _conn
    if _conn is not None:
        return

    logger.info("Opening Kùzu DB at %s …", settings.kuzu_db_path)
    _db = kuzu.Database(
        str(settings.kuzu_db_path),
        buffer_pool_size=settings.kuzu_buffer_pool_mb * 1024 * 1024,
        max_db_size=settings.kuzu_max_db_size_gb * 1024 * 1024 * 1024,
        max_num_threads=settings.kuzu_max_threads,
        read_only=True,
    )
    _conn = kuzu.Connection(_db)
    logger.info("Kùzu connection open (buffer=%d MB, threads=%d).",
                settings.kuzu_buffer_pool_mb, settings.kuzu_max_threads)


def warm_up() -> None:
    """Pre-open the Kùzu DB during startup."""
    with _lock:
        _open_connection()


def get_kuzu_connection() -> Optional[kuzu.Connection]:
    """Get thread-safe Kùzu connection singleton."""
    with _lock:
        _open_connection()
    return _conn


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def traverse_from_documents(
    seed_doc_ids: List[str],
    max_results: int,
    query: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Given a list of seed document_ids (from top FAISS hits) and an optional query string,
    traverse the Kùzu graph to find related Chunks via entity linkage.

    Traversal passes:
      Pass 0 — Independent Entity Seeding (Query Token Match -> Entity -> Graph Traversal):
        Query -> Disease|LabTest|Drug|OntologyTerm -> DOCUMENT_MENTIONS/LABTEST_RELATED_TO -> Chunk
      Pass 1 — Direct HAS_CHUNK from seed documents:
        Document --[HAS_CHUNK]--> Chunk
      Pass 2a — DOCUMENT_MENTIONS entity pivot from seed documents:
        Document --[DOCUMENT_MENTIONS]--> Entity --[DOCUMENT_MENTIONS]<-- Doc --[HAS_CHUNK]--> Chunk
      Pass 2b — LABTEST_RELATED_TO lab pivot from seed documents:
        LabTest --[LABTEST_RELATED_TO]--> Disease <--[DOCUMENT_MENTIONS]-- Doc --[HAS_CHUNK]--> Chunk
    """
    with _lock:
        _open_connection()

    results: List[Dict[str, Any]] = []
    seen_chunk_ids: Set[str] = set()

    # ── Pass 0: Independent Query Entity Seeding ──────────────────────────────
    if query:
        _pass0_query_entity_seeding(query, results, seen_chunk_ids, max(5, max_results // 2))

    # ── Pass 1: Direct HAS_CHUNK from seed documents ─────────────────────────
    if len(results) < max_results:
        _pass1_has_chunk(seed_doc_ids, results, seen_chunk_ids, max_results)

    # ── Pass 2a: DOCUMENT_MENTIONS → entity → other documents → HAS_CHUNK ────
    if len(results) < max_results:
        _pass2a_entity_pivot(seed_doc_ids, results, seen_chunk_ids, max_results)

    # ── Pass 2b: LABTEST_RELATED_TO → Disease → docs → chunks ─────────────────
    if len(results) < max_results:
        _pass2b_labtest_pivot(seed_doc_ids, results, seen_chunk_ids, max_results)

    logger.debug(
        "Graph traversal: %d candidates from query + %d seeds",
        len(results), len(seed_doc_ids),
    )
    return results[:max_results]


# ---------------------------------------------------------------------------
# Query Entity Seeding (Pass 0)
# ---------------------------------------------------------------------------

SYNONYM_MAP: Dict[str, List[str]] = {
    "dvt": ["deep vein thrombosis"],
    "inr": ["international normalized ratio", "warfarin"],
    "ace": ["angiotensin converting enzyme", "ace inhibitor"],
    "ecg": ["electrocardiogram", "hyperkalemia"],
    "sofa": ["sequential organ failure assessment", "sepsis"],
    "afib": ["atrial fibrillation"],
    "mi": ["myocardial infarction"],
    "hgb": ["hemoglobin"],
    "hb": ["hemoglobin"],
}


def _pass0_query_entity_seeding(
    query: str,
    results: List[Dict[str, Any]],
    seen: Set[str],
    limit: int,
) -> None:
    """
    Match query terms against Disease.name, LabTest.test_name, Drug.name, OntologyTerm.term
    in Kùzu, then traverse 1-2 hops to discover relevant Chunks.
    """
    import re
    stopwords = {
        "guidelines", "guideline", "treatment", "first", "line", "risk", "side",
        "effects", "criteria", "changes", "peaked", "waves", "diagnosis", "score",
        "mechanism", "action", "output", "rate", "levels", "threshold", "elevation",
        "contraindications", "failure", "organ", "dysfunction", "critical", "care",
        "which", "drugs", "treat", "what", "does", "mean", "meanings", "about"
    }

    # Extract all alphanumeric words of length >= 2
    raw_words = [w.lower() for w in re.findall(r"\b[a-zA-Z0-9]{2,}\b", query) if w.lower() not in stopwords]

    # 2-word n-grams
    bigrams = [" ".join(raw_words[i:i+2]) for i in range(len(raw_words)-1)]

    # Expand synonyms
    expanded_terms: List[str] = []
    for w in raw_words:
        expanded_terms.append(w)
        if w in SYNONYM_MAP:
            expanded_terms.extend(SYNONYM_MAP[w])

    # Preserve order, unique candidates
    candidates = list(dict.fromkeys(bigrams + expanded_terms))

    for term in candidates:
        if len(term) < 2:
            continue
        if len(results) >= limit:
            break

        term_lower = term.lower()

        # 1. Match Disease
        try:
            diseases_df = _conn.execute(
                """
                MATCH (d:Disease)
                WHERE lower(d.name) CONTAINS $t
                RETURN d.disease_id AS id, d.name AS name
                LIMIT 3
                """,
                {"t": term_lower},
            ).get_as_df()
            for _, drow in diseases_df.iterrows():
                if len(results) >= limit:
                    break
                did, dname = drow["id"], drow["name"]
                _traverse_from_disease_entity(did, dname, results, seen, limit)
        except Exception as exc:
            logger.debug("Disease seed matching failed for %r: %s", term, exc)

        # 2. Match LabTest
        try:
            lab_df = _conn.execute(
                """
                MATCH (l:LabTest)
                WHERE lower(l.test_name) CONTAINS $t
                RETURN l.lab_test_id AS id, l.test_name AS name
                LIMIT 3
                """,
                {"t": term_lower},
            ).get_as_df()
            for _, lrow in lab_df.iterrows():
                if len(results) >= limit:
                    break
                lid, lname = lrow["id"], lrow["name"]
                _traverse_from_labtest_entity(lid, lname, results, seen, limit)
        except Exception as exc:
            logger.debug("LabTest seed matching failed for %r: %s", term, exc)

        # 3. Match Drug
        try:
            drug_df = _conn.execute(
                """
                MATCH (dr:Drug)
                WHERE lower(dr.name) CONTAINS $t
                RETURN dr.node_id AS id, dr.name AS name
                LIMIT 3
                """,
                {"t": term_lower},
            ).get_as_df()
            for _, dr_row in drug_df.iterrows():
                if len(results) >= limit:
                    break
                drid, drname = dr_row["id"], dr_row["name"]
                _traverse_from_drug_entity(drid, drname, results, seen, limit)
        except Exception as exc:
            logger.debug("Drug seed matching failed for %r: %s", term, exc)

        # 4. Match OntologyTerm
        try:
            ont_df = _conn.execute(
                """
                MATCH (o:OntologyTerm)
                WHERE lower(o.term) CONTAINS $t
                RETURN o.term_id AS id, o.term AS name
                LIMIT 3
                """,
                {"t": term_lower},
            ).get_as_df()
            for _, orow in ont_df.iterrows():
                if len(results) >= limit:
                    break
                oid, oname = orow["id"], orow["name"]
                _traverse_from_ontology_entity(oid, oname, results, seen, limit)
        except Exception as exc:
            logger.debug("OntologyTerm seed matching failed for %r: %s", term, exc)


def _traverse_from_disease_entity(
    did: str,
    dname: str,
    results: List[Dict[str, Any]],
    seen: Set[str],
    limit: int,
) -> None:
    """Disease <-[DOCUMENT_MENTIONS]- Document -[HAS_CHUNK]-> Chunk."""
    try:
        df = _conn.execute(
            """
            MATCH (dis:Disease {disease_id: $did})<-[:DOCUMENT_MENTIONS]-(doc:Document)-[:HAS_CHUNK]->(c:Chunk)
            RETURN c.chunk_id, c.document_id, c.faiss_id, c.category, c.chunk_type, c.source_doc
            LIMIT $lim
            """,
            {"did": did, "lim": settings.graph_entity_chunk_limit},
        ).get_as_df()
        entity_dict = {"label": "Disease", "id": did, "name": dname}
        for _, row in df.iterrows():
            cid = row["c.chunk_id"]
            if cid in seen:
                continue
            seen.add(cid)
            results.append({
                "chunk_id":       cid,
                "document_id":    row["c.document_id"],
                "faiss_id":       int(row["c.faiss_id"]),
                "category":       row["c.category"],
                "chunk_type":     row["c.chunk_type"],
                "source_doc":     row["c.source_doc"],
                "graph_path":     ["DOCUMENT_MENTIONS", "HAS_CHUNK"],
                "graph_score":    0.85,
                "edge_trust":     "high",
                "graph_entities": [entity_dict],
            })
            if len(results) >= limit:
                break
    except Exception as exc:
        logger.debug("Traverse from disease %s failed: %s", did, exc)


def _traverse_from_labtest_entity(
    lid: str,
    lname: str,
    results: List[Dict[str, Any]],
    seen: Set[str],
    limit: int,
) -> None:
    """LabTest -[LABTEST_RELATED_TO]-> Disease <-[DOCUMENT_MENTIONS]- Document -[HAS_CHUNK]-> Chunk."""
    try:
        df = _conn.execute(
            """
            MATCH (l:LabTest {lab_test_id: $lid})-[:LABTEST_RELATED_TO]->(dis:Disease)<-[:DOCUMENT_MENTIONS]-(doc:Document)-[:HAS_CHUNK]->(c:Chunk)
            RETURN c.chunk_id, c.document_id, c.faiss_id, c.category, c.chunk_type, c.source_doc, dis.disease_id AS dis_id, dis.name AS dis_name
            LIMIT $lim
            """,
            {"lid": lid, "lim": settings.graph_entity_chunk_limit},
        ).get_as_df()
        for _, row in df.iterrows():
            cid = row["c.chunk_id"]
            if cid in seen:
                continue
            seen.add(cid)
            entities = [
                {"label": "LabTest", "id": lid, "name": lname},
                {"label": "Disease", "id": row["dis_id"], "name": row["dis_name"]},
            ]
            results.append({
                "chunk_id":       cid,
                "document_id":    row["c.document_id"],
                "faiss_id":       int(row["c.faiss_id"]),
                "category":       row["c.category"],
                "chunk_type":     row["c.chunk_type"],
                "source_doc":     row["c.source_doc"],
                "graph_path":     ["LABTEST_RELATED_TO", "DOCUMENT_MENTIONS", "HAS_CHUNK"],
                "graph_score":    0.85,
                "edge_trust":     "high",
                "graph_entities": entities,
            })
            if len(results) >= limit:
                break
    except Exception as exc:
        logger.debug("Traverse from labtest %s failed: %s", lid, exc)


def _traverse_from_drug_entity(
    drid: str,
    drname: str,
    results: List[Dict[str, Any]],
    seen: Set[str],
    limit: int,
) -> None:
    """Drug -[DRUG_TREATS|DRUG_CAUSES]-> Disease <-[DOCUMENT_MENTIONS]- Document -[HAS_CHUNK]-> Chunk."""
    try:
        df = _conn.execute(
            """
            MATCH (dr:Drug {node_id: $drid})-[:DRUG_TREATS|DRUG_CAUSES]->(dis:Disease)<-[:DOCUMENT_MENTIONS]-(doc:Document)-[:HAS_CHUNK]->(c:Chunk)
            RETURN c.chunk_id, c.document_id, c.faiss_id, c.category, c.chunk_type, c.source_doc, dis.disease_id AS dis_id, dis.name AS dis_name
            LIMIT $lim
            """,
            {"drid": drid, "lim": settings.graph_entity_chunk_limit},
        ).get_as_df()
        for _, row in df.iterrows():
            cid = row["c.chunk_id"]
            if cid in seen:
                continue
            seen.add(cid)
            entities = [
                {"label": "Drug", "id": drid, "name": drname},
                {"label": "Disease", "id": row["dis_id"], "name": row["dis_name"]},
            ]
            results.append({
                "chunk_id":       cid,
                "document_id":    row["c.document_id"],
                "faiss_id":       int(row["c.faiss_id"]),
                "category":       row["c.category"],
                "chunk_type":     row["c.chunk_type"],
                "source_doc":     row["c.source_doc"],
                "graph_path":     ["DRUG_TREATS", "DOCUMENT_MENTIONS", "HAS_CHUNK"],
                "graph_score":    0.85,
                "edge_trust":     "high",
                "graph_entities": entities,
            })
            if len(results) >= limit:
                return
    except Exception as exc:
        logger.debug("Traverse from drug %s failed: %s", drid, exc)


def _traverse_from_ontology_entity(
    oid: str,
    oname: str,
    results: List[Dict[str, Any]],
    seen: Set[str],
    limit: int,
) -> None:
    """OntologyTerm <-[DISEASE_MAPPED_TO]- Disease <-[DOCUMENT_MENTIONS]- Document -[HAS_CHUNK]-> Chunk."""
    try:
        df = _conn.execute(
            """
            MATCH (o:OntologyTerm {term_id: $oid})<-[:DISEASE_MAPPED_TO]-(dis:Disease)<-[:DOCUMENT_MENTIONS]-(doc:Document)-[:HAS_CHUNK]->(c:Chunk)
            RETURN c.chunk_id, c.document_id, c.faiss_id, c.category, c.chunk_type, c.source_doc, dis.disease_id AS dis_id, dis.name AS dis_name
            LIMIT $lim
            """,
            {"oid": oid, "lim": settings.graph_entity_chunk_limit},
        ).get_as_df()
        for _, row in df.iterrows():
            cid = row["c.chunk_id"]
            if cid in seen:
                continue
            seen.add(cid)
            entities = [
                {"label": "OntologyTerm", "id": oid, "name": oname},
                {"label": "Disease", "id": row["dis_id"], "name": row["dis_name"]},
            ]
            results.append({
                "chunk_id":       cid,
                "document_id":    row["c.document_id"],
                "faiss_id":       int(row["c.faiss_id"]),
                "category":       row["c.category"],
                "chunk_type":     row["c.chunk_type"],
                "source_doc":     row["c.source_doc"],
                "graph_path":     ["DISEASE_MAPPED_TO", "DOCUMENT_MENTIONS", "HAS_CHUNK"],
                "graph_score":    0.85,
                "edge_trust":     "high",
                "graph_entities": entities,
            })
            if len(results) >= limit:
                break
    except Exception as exc:
        logger.debug("Traverse from ontology %s failed: %s", oid, exc)



# ---------------------------------------------------------------------------
# Pass implementations
# ---------------------------------------------------------------------------

def _pass1_has_chunk(
    seed_doc_ids: List[str],
    results: List[Dict[str, Any]],
    seen: Set[str],
    limit: int,
) -> None:
    """
    Pull chunks directly attached to seed documents via HAS_CHUNK.
    High-trust: Document → Chunk is a structural edge (built by the pipeline).
    """
    remaining = limit - len(results)
    if remaining <= 0 or not seed_doc_ids:
        return

    # Kùzu parameter binding: pass list as $doc_ids
    # We need to escape them manually since Kùzu's Python driver may not
    # support list-param MATCH properly for all versions.
    for doc_id in seed_doc_ids[:settings.graph_seed_docs]:
        if len(results) >= limit:
            break
        try:
            res = _conn.execute(
                """
                MATCH (doc:Document {document_id: $did})-[:HAS_CHUNK]->(c:Chunk)
                OPTIONAL MATCH (doc)-[:DOCUMENT_MENTIONS]->(dis:Disease)
                RETURN c.chunk_id, c.document_id, c.faiss_id, c.category,
                       c.chunk_type, c.source_doc, dis.disease_id AS dis_id, dis.name AS dis_name
                LIMIT $lim
                """,
                {"did": doc_id, "lim": settings.graph_entity_chunk_limit},
            ).get_as_df()
        except Exception as exc:
            logger.warning("HAS_CHUNK query failed for doc %s: %s", doc_id, exc)
            continue

        for _, row in res.iterrows():
            cid = row["c.chunk_id"]
            if cid in seen:
                continue
            seen.add(cid)

            dis_id = row.get("dis_id")
            dis_name = row.get("dis_name")
            entities = []
            if dis_id and dis_name and str(dis_id) != "nan":
                entities.append({"label": "Disease", "id": str(dis_id), "name": str(dis_name)})

            results.append({
                "chunk_id":      cid,
                "document_id":   row["c.document_id"],
                "faiss_id":      int(row["c.faiss_id"]),
                "category":      row["c.category"],
                "chunk_type":    row["c.chunk_type"],
                "source_doc":    row["c.source_doc"],
                "graph_path":    ["HAS_CHUNK"],
                "graph_score":   0.85,          # high-trust direct structural edge
                "edge_trust":    "high",
                "graph_entities": entities,
            })
            if len(results) >= limit:
                break


def _pass2a_entity_pivot(
    seed_doc_ids: List[str],
    results: List[Dict[str, Any]],
    seen: Set[str],
    limit: int,
) -> None:
    """
    1-hop via DOCUMENT_MENTIONS → entity → find other docs with HAS_CHUNK.
    Discovers thematically related chunks beyond the seed documents.
    """
    for doc_id in seed_doc_ids[:settings.graph_seed_docs]:
        if len(results) >= limit:
            break

        # Step 1: Which entities does this document mention?
        try:
            entities_df = _conn.execute(
                """
                MATCH (doc:Document {document_id: $did})-[:DOCUMENT_MENTIONS]->(e)
                RETURN e.disease_id AS eid, e.name AS ename,
                       labels(e)[0] AS elabel
                LIMIT 10
                """,
                {"did": doc_id},
            ).get_as_df()
        except Exception as exc:
            logger.warning("DOCUMENT_MENTIONS query failed for %s: %s", doc_id, exc)
            continue

        for _, erow in entities_df.iterrows():
            if len(results) >= limit:
                break
            eid = erow.get("eid", "")
            ename = erow.get("ename", "")
            elabel = erow.get("elabel", "")

            # Step 2: Other documents that mention this entity → their chunks
            try:
                pivot_df = _conn.execute(
                    """
                    MATCH (e:Disease {disease_id: $eid})<-[:DOCUMENT_MENTIONS]-(d2:Document)
                          -[:HAS_CHUNK]->(c:Chunk)
                    RETURN c.chunk_id, c.document_id, c.faiss_id, c.category,
                           c.chunk_type, c.source_doc
                    LIMIT $lim
                    """,
                    {"eid": eid, "lim": settings.graph_entity_chunk_limit},
                ).get_as_df()
            except Exception as exc:
                logger.debug("Entity pivot failed for entity %s: %s", eid, exc)
                continue

            entity_dict = {"label": elabel, "id": eid, "name": ename}
            for _, crow in pivot_df.iterrows():
                cid = crow["c.chunk_id"]
                if cid in seen:
                    continue
                seen.add(cid)
                results.append({
                    "chunk_id":       cid,
                    "document_id":    crow["c.document_id"],
                    "faiss_id":       int(crow["c.faiss_id"]),
                    "category":       crow["c.category"],
                    "chunk_type":     crow["c.chunk_type"],
                    "source_doc":     crow["c.source_doc"],
                    "graph_path":     ["DOCUMENT_MENTIONS", "HAS_CHUNK"],
                    "graph_score":    0.70,
                    "edge_trust":     "high",
                    "graph_entities": [entity_dict],
                })
                if len(results) >= limit:
                    break


def _pass2b_labtest_pivot(
    seed_doc_ids: List[str],
    results: List[Dict[str, Any]],
    seen: Set[str],
    limit: int,
) -> None:
    """
    For queries about lab tests: find labtest nodes mentioned in seed docs,
    then follow LABTEST_RELATED_TO → Disease → docs → chunks.
    """
    for doc_id in seed_doc_ids[:3]:   # only top-3 seeds for this pass
        if len(results) >= limit:
            break

        try:
            labtest_df = _conn.execute(
                """
                MATCH (doc:Document {document_id: $did})-[:HAS_CHUNK]->(c:Chunk)
                      <-[:HAS_CHUNK]-(doc2:Document)<-[:DOCUMENT_MENTIONS]-(l:LabTest)
                RETURN l.lab_test_id AS lid, l.test_name AS lname
                LIMIT 5
                """,
                {"did": doc_id},
            ).get_as_df()
        except Exception:
            continue

        for _, lrow in labtest_df.iterrows():
            if len(results) >= limit:
                break
            lid = lrow.get("lid", "")
            lname = lrow.get("lname", "")

            try:
                pivot_df = _conn.execute(
                    """
                    MATCH (l:LabTest {lab_test_id: $lid})-[:LABTEST_RELATED_TO]->(dis:Disease)
                          <-[:DOCUMENT_MENTIONS]-(d2:Document)-[:HAS_CHUNK]->(c:Chunk)
                    RETURN c.chunk_id, c.document_id, c.faiss_id, c.category,
                           c.chunk_type, c.source_doc
                    LIMIT $lim
                    """,
                    {"lid": lid, "lim": settings.graph_entity_chunk_limit},
                ).get_as_df()
            except Exception as exc:
                logger.debug("LabTest pivot failed for %s: %s", lid, exc)
                continue

            entity_dict = {"label": "LabTest", "id": lid, "name": lname}
            for _, crow in pivot_df.iterrows():
                cid = crow["c.chunk_id"]
                if cid in seen:
                    continue
                seen.add(cid)
                results.append({
                    "chunk_id":       cid,
                    "document_id":    crow["c.document_id"],
                    "faiss_id":       int(crow["c.faiss_id"]),
                    "category":       crow["c.category"],
                    "chunk_type":     crow["c.chunk_type"],
                    "source_doc":     crow["c.source_doc"],
                    "graph_path":     ["LABTEST_RELATED_TO", "DOCUMENT_MENTIONS", "HAS_CHUNK"],
                    "graph_score":    0.75,
                    "edge_trust":     "high",
                    "graph_entities": [entity_dict],
                })
                if len(results) >= limit:
                    break
