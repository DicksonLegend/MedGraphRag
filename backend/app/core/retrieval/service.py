"""
MedGraphRAG Backend — Hybrid Retrieval Service
================================================
Orchestrates the full retrieval pipeline:

  1. Embed query (CPU, MedCPT-Query-Encoder)
  2. FAISS vector search (CPU IVFpq)
  3. Category balancing (suppress lab_reference dominance)
  4. Graph traversal (Kùzu, seeded by top FAISS doc_ids)
  5. RRF fusion (FAISS list + graph list)
  6. Text loading (O(1) random access into chunks.jsonl)
  7. Pack EvidenceItems + RetrievalResult

Parameterized by `destination` (default "global") — the same code
will serve per-user private indexes in a future step.

Thread safety: all component singletons (FAISS, Kùzu, embedder) are
independently thread-safe. HybridRetrievalService itself is stateless.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.retrieval import embedder, faiss_store, graph_store
from app.core.retrieval.fusion import apply_category_caps, rrf_fuse
from app.core.retrieval.schemas import (
    EvidenceItem,
    GraphTraversalStats,
    RetrievalRequest,
    RetrievalResult,
)

logger = logging.getLogger(__name__)


class HybridRetrievalService:
    """
    Stateless service class for hybrid vector + graph retrieval.

    Usage
    -----
    service = HybridRetrievalService()
    result = service.retrieve(RetrievalRequest(query="warfarin INR monitoring"))
    """

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        """
        Execute the full hybrid retrieval pipeline.

        Parameters
        ----------
        request : RetrievalRequest

        Returns
        -------
        RetrievalResult with ranked EvidenceItems.
        """
        t_total_start = time.perf_counter()
        top_n = request.top_n or settings.retrieval_top_n
        latency_breakdown: Dict[str, float] = {}

        # ── Stage 1: Query Embedding ─────────────────────────────────────────
        t0 = time.perf_counter()
        query_vec = embedder.embed_query(request.query)
        latency_breakdown["embed_ms"] = (time.perf_counter() - t0) * 1000
        logger.info("[Stage 1] Embed: %.1f ms", latency_breakdown["embed_ms"])

        # ── Stage 2: FAISS Search ────────────────────────────────────────────
        t0 = time.perf_counter()
        raw_faiss = faiss_store.search(
            query_vector=query_vec,
            top_k=settings.faiss_top_k_raw,
            category_filter=request.category_filter,
            destination=request.destination,
        )
        latency_breakdown["faiss_ms"] = (time.perf_counter() - t0) * 1000
        logger.info(
            "[Stage 2] FAISS: %d raw hits in %.1f ms",
            len(raw_faiss), latency_breakdown["faiss_ms"],
        )

        # ── Stage 3: Category Balancing ──────────────────────────────────────
        balanced_faiss = apply_category_caps(raw_faiss)
        logger.info(
            "[Stage 3] Category balancing: %d → %d candidates",
            len(raw_faiss), len(balanced_faiss),
        )

        # ── Stage 4: Graph Traversal ─────────────────────────────────────────
        t0 = time.perf_counter()
        if settings.retrieval_graph_enabled:
            # Extract unique doc_ids from top FAISS hits for seeding
            seed_doc_ids = self._extract_seed_docs(balanced_faiss)

            graph_candidates = graph_store.traverse_from_documents(
                seed_doc_ids=seed_doc_ids,
                max_results=settings.graph_max_results,
                query=request.query,
            )
        else:
            seed_doc_ids = []
            graph_candidates = []

        latency_breakdown["graph_ms"] = (time.perf_counter() - t0) * 1000
        logger.info(
            "[Stage 4] Graph: %d candidates from %d seeds in %.1f ms",
            len(graph_candidates), len(seed_doc_ids), latency_breakdown["graph_ms"],
        )

        # ── Stage 5: RRF Fusion ──────────────────────────────────────────────
        t0 = time.perf_counter()
        fused = rrf_fuse(balanced_faiss, graph_candidates)
        latency_breakdown["fuse_ms"] = (time.perf_counter() - t0) * 1000
        logger.info(
            "[Stage 5] Fusion: %d merged, %.1f ms",
            len(fused), latency_breakdown["fuse_ms"],
        )

        # ── Stage 6: Text Loading ────────────────────────────────────────────
        t0 = time.perf_counter()
        top_fused = fused[:top_n]
        faiss_ids_to_load = [
            item["faiss_id"] for item in top_fused if item["faiss_id"] >= 0
        ]
        chunk_texts = faiss_store.batch_load_chunk_texts(faiss_ids_to_load)
        latency_breakdown["text_load_ms"] = (time.perf_counter() - t0) * 1000
        logger.info(
            "[Stage 6] Text load: %d chunks in %.1f ms",
            len(faiss_ids_to_load), latency_breakdown["text_load_ms"],
        )

        # ── Stage 7: Pack EvidenceItems ──────────────────────────────────────
        evidence_items = []
        for item in top_fused:
            fid = item["faiss_id"]
            raw_text = item.get("text_snippet", "") if fid < 0 else chunk_texts.get(fid, "")
            snippet = raw_text[: settings.text_snippet_max_chars]

            evidence_items.append(
                EvidenceItem(
                    chunk_id=item["chunk_id"],
                    document_id=item["document_id"],
                    faiss_id=fid,
                    category=item["category"],
                    chunk_type=item["chunk_type"],
                    source=item.get("source", item.get("source_doc", "")),
                    title=item.get("title"),
                    text_snippet=snippet,
                    faiss_score=item["faiss_score"],
                    graph_score=item["graph_score"],
                    fused_score=item["fused_score"],
                    graph_boost_applied=item["graph_boost_applied"],
                    graph_path=item["graph_path"],
                    graph_entities=item["graph_entities"],
                    graph_path_str=item.get("graph_path_str"),
                    edge_trust=item["edge_trust"],
                    source_type=item["source_type"],
                )
            )

        # ── Graph diagnostic stats ────────────────────────────────────────────
        distinct_edge_labels: set = set()
        entities_reached: set = set()
        graph_only_count = 0
        for item in top_fused:
            for ep in item.get("graph_path", []):
                distinct_edge_labels.add(ep)
            for ent in item.get("graph_entities", []):
                entities_reached.add(ent.get("id", ""))
            if item["source_type"] == "graph":
                graph_only_count += 1

        graph_stats = GraphTraversalStats(
            seeds_used=len(seed_doc_ids),
            entities_reached=len(entities_reached),
            chunks_from_graph=graph_only_count,
            edges_traversed=sorted(distinct_edge_labels),
        )

        total_ms = (time.perf_counter() - t_total_start) * 1000
        latency_breakdown["total_ms"] = total_ms

        logger.info(
            "Retrieval complete: %d items, total %.1f ms [query=%r]",
            len(evidence_items), total_ms, request.query[:60],
        )

        return RetrievalResult(
            query=request.query,
            destination=request.destination,
            items=evidence_items,
            total_faiss_candidates=len(raw_faiss),
            total_graph_candidates=len(graph_candidates),
            graph_stats=graph_stats,
            latency_ms=total_ms,
            latency_breakdown_ms=latency_breakdown,
        )

    # -------------------------------------------------------------------------

    def _extract_seed_docs(self, faiss_candidates: List[Dict[str, Any]]) -> List[str]:
        """
        Extract unique document_ids from FAISS candidates for graph seeding.
        Priority: unique docs from top-scoring candidates.
        """
        seen: set = set()
        docs: List[str] = []
        for item in faiss_candidates:
            doc_id = item.get("document_id", "")
            if doc_id and doc_id not in seen:
                seen.add(doc_id)
                docs.append(doc_id)
            if len(docs) >= settings.graph_seed_docs:
                break
        return docs
