"""
MedGraphRAG Backend — Reciprocal Rank Fusion + Category Balancing
====================================================================
Fuses FAISS vector-search results with graph-traversal candidates.

Algorithm
---------
1. Category balancing (FAISS side):
   - Apply per-category hard caps (config.category_max_chunks).
   - lab_reference has a tight cap (default 8) because it's 71.7% of the index.

2. RRF (standard formula):
   rrf_score(d) = Σ_i  weight_i / (k + rank_i(d))

   where i ∈ {faiss_list, graph_list}.

3. Graph boost:
   If a FAISS chunk is also reachable via a high-trust graph edge:
   fused_score += graph_boost (default 0.15)

4. Low-trust penalty:
   If a graph-only chunk was reached exclusively via low-trust edges:
   graph_score *= low_trust_score_penalty (default 0.5)

5. Final ranking:
   Sort by fused_score descending, take top retrieval_top_n.

References
----------
Cormack et al., 2009 "Reciprocal Rank Fusion outperforms Condorcet and
individual Rank Learning Methods."
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Category balancing
# ---------------------------------------------------------------------------

def apply_category_caps(
    faiss_results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Apply per-category hard caps to the raw FAISS results list.

    Parameters
    ----------
    faiss_results : list of dict (sorted by score descending)
        Each dict must contain at least 'category' and 'faiss_score'.

    Returns
    -------
    Filtered list, same order, with at most config.category_max_chunks[cat]
    items per category, and at most config.faiss_final_k total.
    """
    cat_counts: Dict[str, int] = {}
    capped: List[Dict[str, Any]] = []
    default_cap = settings.faiss_final_k  # uncapped categories: use global limit

    for item in faiss_results:
        cat = item.get("category", "unknown")
        max_for_cat = settings.category_max_chunks.get(cat, default_cap)
        if cat_counts.get(cat, 0) < max_for_cat:
            capped.append(item)
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
        if len(capped) >= settings.faiss_final_k:
            break

    logger.debug(
        "Category caps applied: %d → %d candidates. Per-cat: %s",
        len(faiss_results), len(capped), cat_counts,
    )
    return capped


# ---------------------------------------------------------------------------
# Document-Level Deduplication
# ---------------------------------------------------------------------------

def get_canonical_doc_id(doc_id: str) -> str:
    """Extract canonical document identifier (e.g. PMID_38823454 from subfolder paths)."""
    if not doc_id:
        return ""
    return doc_id.split("/")[-1]


def apply_document_dedup(
    candidates: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Group candidates by canonical document_id (basename) and keep ONLY the chunk
    with the highest fused_score for each canonical document_id.
    Discard all subsequent duplicate chunks belonging to the same document.

    Parameters
    ----------
    candidates : list of dict (sorted by fused_score descending)

    Returns
    -------
    Deduplicated list of candidate dicts (at most 1 chunk per canonical document).
    """
    seen_docs: Set[str] = set()
    deduped: List[Dict[str, Any]] = []
    discarded_count = 0

    for item in candidates:
        raw_doc_id = item.get("document_id", "")
        canon_id = get_canonical_doc_id(raw_doc_id)
        if not canon_id:
            deduped.append(item)
            continue
        if canon_id not in seen_docs:
            seen_docs.add(canon_id)
            deduped.append(item)
        else:
            discarded_count += 1

    logger.info(
        "Document-level dedup: kept %d chunks, discarded %d duplicate chunks.",
        len(deduped), discarded_count,
    )
    return deduped


# ---------------------------------------------------------------------------
# RRF Fusion
# ---------------------------------------------------------------------------

def rrf_fuse(
    faiss_candidates: List[Dict[str, Any]],
    graph_candidates: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Fuse FAISS and graph candidates using Reciprocal Rank Fusion.

    Parameters
    ----------
    faiss_candidates : list of dicts (category-balanced, sorted by score desc)
        Keys: faiss_id, chunk_id, document_id, category, chunk_type, source,
              title, faiss_score, token_count, subcategory, subpath.
    graph_candidates : list of dicts (from graph_store.traverse_from_documents)
        Keys: chunk_id, document_id, faiss_id, category, chunk_type, source_doc,
              graph_path, graph_score, edge_trust, graph_entities.

    Returns
    -------
    Merged list of dicts (deduplicated by document_id) with keys from both sides,
    plus: fused_score, source_type ('faiss'|'graph'|'both'), graph_boost_applied.
    Sorted by fused_score descending.
    """
    k = settings.rrf_k
    w_faiss = settings.rrf_faiss_weight
    w_graph = settings.rrf_graph_weight
    boost = settings.graph_boost
    penalty = settings.low_trust_score_penalty

    # ── Build lookup by chunk_id ─────────────────────────────────────────────
    merged: Dict[str, Dict[str, Any]] = {}

    # --- FAISS side ---
    for rank, item in enumerate(faiss_candidates, start=1):
        cid = item["chunk_id"]
        rrf_contribution = w_faiss / (k + rank)
        if cid not in merged:
            merged[cid] = {
                # Core provenance (FAISS side)
                "chunk_id":         cid,
                "document_id":      item.get("document_id", ""),
                "faiss_id":         item.get("faiss_id", -1),
                "category":         item.get("category", "unknown"),
                "chunk_type":       item.get("chunk_type", "prose"),
                "source":           item.get("source", ""),
                "title":            item.get("title"),
                "token_count":      item.get("token_count", 0),
                # Scores
                "faiss_score":      item.get("faiss_score", 0.0),
                "graph_score":      0.0,
                "fused_score":      rrf_contribution,
                # Graph provenance (to be filled by graph side)
                "graph_path":       [],
                "graph_entities":   [],
                "edge_trust":       "none",
                "graph_boost_applied": False,
                "source_type":      "faiss",
            }
        else:
            merged[cid]["fused_score"] += rrf_contribution
            merged[cid]["source_type"] = "both"

    # --- Graph side ---
    for rank, item in enumerate(graph_candidates, start=1):
        cid = item["chunk_id"]
        faiss_id = item.get("faiss_id", -1)
        raw_graph_score = item.get("graph_score", 0.5)

        # Apply low-trust penalty
        edge_trust = item.get("edge_trust", "none")
        if edge_trust == "low":
            raw_graph_score *= penalty

        rrf_contribution = w_graph / (k + rank)

        if cid not in merged:
            # Graph-only chunk — only appears if faiss_id > 0 (it has an embedding)
            merged[cid] = {
                "chunk_id":         cid,
                "document_id":      item.get("document_id", ""),
                "faiss_id":         faiss_id,
                "category":         item.get("category", "unknown"),
                "chunk_type":       item.get("chunk_type", "prose"),
                "source":           item.get("source_doc", ""),
                "title":            None,
                "token_count":      0,
                "faiss_score":      0.0,
                "graph_score":      raw_graph_score,
                "fused_score":      rrf_contribution,
                "graph_path":       item.get("graph_path", []),
                "graph_entities":   item.get("graph_entities", []),
                "edge_trust":       edge_trust,
                "graph_boost_applied": False,
                "source_type":      "graph",
            }
        else:
            # Seen in FAISS already → corroborated by graph
            merged[cid]["fused_score"]    += rrf_contribution
            merged[cid]["graph_score"]     = raw_graph_score
            merged[cid]["graph_path"]      = item.get("graph_path", [])
            merged[cid]["graph_entities"]  = item.get("graph_entities", [])
            merged[cid]["edge_trust"]      = edge_trust
            merged[cid]["source_type"]     = "both"

            # Apply graph boost for high-trust edge corroboration
            if edge_trust == "high":
                merged[cid]["fused_score"] += boost
                merged[cid]["graph_boost_applied"] = True

    # ── Sort by fused_score ─────────────────────────────────────────────────
    ranked = sorted(merged.values(), key=lambda x: x["fused_score"], reverse=True)

    # ── Document-level deduplication ─────────────────────────────────────────
    deduped = apply_document_dedup(ranked)

    logger.debug(
        "RRF fusion: %d FAISS + %d graph → %d merged → %d deduped candidates",
        len(faiss_candidates), len(graph_candidates), len(ranked), len(deduped),
    )
    return deduped

