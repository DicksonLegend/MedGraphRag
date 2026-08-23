#!/usr/bin/env python3
"""
MedGraphRAG — Baseline Retrieval Methods
=========================================
Implements standard baseline retrieval methods for comparison:
1. BM25 (lexical/sparse retrieval) — streaming, top-pool only
2. Dense Vector (FAISS-only, no graph)
3. Hybrid RRF (FAISS + BM25, no graph) — streaming, top-pool only
4. Graph-only (Kuzu traversal only)
5. Full MedGraphRAG (FAISS + Graph + RRF) - reference

All baselines use the same evaluation queries and metrics for fair comparison.

Memory-safety fix: BM25Retriever and HybridRRFRetriever now build a tiny
BM25Okapi index ONLY over the FAISS top candidate_pool (default 200) per query,
using faiss_store.batch_load_chunk_texts for O(1) random access. This avoids
loading the full 2.3M-chunk corpus into RAM.
"""

from __future__ import annotations

import gc
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from app.config import settings
from app.core.retrieval import faiss_store, graph_store, embedder
from app.core.retrieval.schemas import RetrievalRequest, RetrievalResult, EvidenceItem, GraphTraversalStats
from app.core.retrieval.service import HybridRetrievalService

logger = logging.getLogger(__name__)

# ─── Memory-safety constants (tunable via env if needed) ───
# Defaults now come from config (MEDGRAPH_BM25_CANDIDATE_POOL, MEDGRAPH_BM25_BATCH_SIZE)
BM25_CANDIDATE_POOL = settings.bm25_candidate_pool     # FAISS candidates to build per-query BM25 over
BM25_BATCH_SIZE = settings.bm25_batch_size             # batch size for batch_load_chunk_texts

# Default test queries for baseline evaluation
BASELINE_QUERIES = [
    "warfarin INR monitoring guidelines atrial fibrillation",
    "ACE inhibitor hypertension treatment first line",
    "critical hemoglobin levels anemia transfusion threshold",
    "troponin elevation myocardial infarction diagnosis",
    "metformin type 2 diabetes contraindications renal failure",
    "aspirin dosing secondary prevention coronary artery disease",
    "direct oral anticoagulant reversal agent andexanet alfa",
    "sepsis bundle lactate clearance antibiotics timing",
    "heart failure reduced ejection fraction guideline directed medical therapy",
    "pneumonia CURB-65 score outpatient management criteria",
]


class BaselineRetriever:
    """Base class for baseline retrievers."""

    def __init__(self, name: str):
        self.name = name
        self._faiss_initialized = False

    def _ensure_faiss(self):
        if not self._faiss_initialized:
            faiss_store.warm_up()
            self._faiss_initialized = True

    def retrieve(self, query: str, top_n: int = 10) -> RetrievalResult:
        """Retrieve documents for a query. Must be implemented by subclasses."""
        raise NotImplementedError


class BM25Retriever(BaselineRetriever):
    """
    BM25 sparse retrieval baseline — memory-safe streaming version.
    Builds a tiny BM25Okapi index over FAISS top candidate_pool per query.
    """

    def __init__(self, candidate_pool: int = BM25_CANDIDATE_POOL, batch_size: int = BM25_BATCH_SIZE):
        super().__init__("BM25")
        self.candidate_pool = candidate_pool
        self.batch_size = batch_size

    def retrieve(self, query: str, top_n: int = 10) -> RetrievalResult:
        self._ensure_faiss()
        t0 = time.perf_counter()

        # 1. Get FAISS top candidate_pool (cheap: index + sidecar already in RAM)
        query_vec = embedder.embed_query(query)
        faiss_results = faiss_store.search(query_vec, self.candidate_pool)

        if not faiss_results:
            latency_ms = (time.perf_counter() - t0) * 1000
            return RetrievalResult(
                query=query,
                destination="global",
                items=[],
                total_faiss_candidates=0,
                total_graph_candidates=0,
                graph_stats=GraphTraversalStats(seeds_used=0, entities_reached=0, chunks_from_graph=0, edges_traversed=[]),
                latency_ms=latency_ms,
                latency_breakdown_ms={"faiss_search": latency_ms},
            )

        # 2. Extract faiss_ids and load ONLY those texts (O(1) seeks via offsets)
        faiss_ids = [r["faiss_id"] for r in faiss_results]
        id_to_text = faiss_store.batch_load_chunk_texts(faiss_ids)

        # 3. Build tiny BM25 over candidate_pool docs (≤200)
        tokenized_corpus = []
        valid_faiss_ids = []
        for fid in faiss_ids:
            text = id_to_text.get(fid, "")
            if text:
                tokenized_corpus.append(text.lower().split())
                valid_faiss_ids.append(fid)

        if not tokenized_corpus:
            latency_ms = (time.perf_counter() - t0) * 1000
            return RetrievalResult(
                query=query,
                destination="global",
                items=[],
                total_faiss_candidates=len(faiss_results),
                total_graph_candidates=0,
                graph_stats=GraphTraversalStats(seeds_used=0, entities_reached=0, chunks_from_graph=0, edges_traversed=[]),
                latency_ms=latency_ms,
                latency_breakdown_ms={"faiss_search": latency_ms},
            )

        # Lazy import (rank_bm25 already in venv)
        from rank_bm25 import BM25Okapi
        bm25 = BM25Okapi(tokenized_corpus)

        # 4. Score query against candidate pool
        tokenized_query = query.lower().split()
        scores = bm25.get_scores(tokenized_query)

        # 5. Top-N by BM25 score within the pool
        top_local = np.argsort(scores)[::-1][:top_n]

        # 6. Build EvidenceItems from faiss_results[local_idx] metadata
        items = []
        for rank, local_idx in enumerate(top_local):
            fid = valid_faiss_ids[local_idx]
            # Find matching faiss_result for metadata
            meta = None
            for r in faiss_results:
                if r["faiss_id"] == fid:
                    meta = r
                    break
            if meta is None:
                continue

            items.append(EvidenceItem(
                chunk_id=meta.get("chunk_id", f"bm25_{fid}"),
                document_id=meta.get("document_id", "unknown"),
                faiss_id=int(fid),
                text_snippet=meta.get("text_snippet", "")[:500],
                category=meta.get("category", "unknown"),
                chunk_type=meta.get("chunk_type", "body"),
                source=meta.get("source", "unknown"),
                title=meta.get("title"),
                fused_score=float(scores[local_idx]),
                faiss_score=0.0,
                graph_score=0.0,
                source_type="faiss",  # BM25 scores FAISS candidates
                graph_path=[],
                graph_entities=[],
                graph_path_str=None,
            ))

        latency_ms = (time.perf_counter() - t0) * 1000

        return RetrievalResult(
            query=query,
            destination="global",
            items=items,
            total_faiss_candidates=len(faiss_results),
            total_graph_candidates=0,
            graph_stats=GraphTraversalStats(seeds_used=0, entities_reached=0, chunks_from_graph=0, edges_traversed=[]),
            latency_ms=latency_ms,
            latency_breakdown_ms={"faiss_search": latency_ms, "bm25_scoring": 0},
        )


class DenseVectorRetriever(BaselineRetriever):
    """
    Dense vector retrieval only (FAISS, no graph).
    """

    def __init__(self):
        super().__init__("DenseVector")
        self._ensure_faiss()

    def retrieve(self, query: str, top_n: int = 10) -> RetrievalResult:
        t0 = time.perf_counter()

        # Embed query
        query_vec = embedder.embed_query(query)

        # Search FAISS using module-level function
        results = faiss_store.search(query_vec, top_n * 2)

        # Convert results to EvidenceItems
        items = []
        for rank, meta in enumerate(results):
            if rank >= top_n:
                break
            items.append(EvidenceItem(
                chunk_id=meta.get("chunk_id", f"dense_{meta.get('faiss_id', rank)}"),
                document_id=meta.get("document_id", "unknown"),
                faiss_id=int(meta.get("faiss_id", rank)),
                text_snippet=meta.get("text_snippet", "")[:500],
                category=meta.get("category", "unknown"),
                chunk_type=meta.get("chunk_type", "body"),
                source=meta.get("source", "unknown"),
                title=meta.get("title"),
                fused_score=float(meta.get("faiss_score", 0.0)),
                faiss_score=float(meta.get("faiss_score", 0.0)),
                graph_score=0.0,
                source_type="faiss",
                graph_path=[],
                graph_entities=[],
                graph_path_str=None,
            ))

        latency_ms = (time.perf_counter() - t0) * 1000

        return RetrievalResult(
            query=query,
            destination="global",
            items=items,
            total_faiss_candidates=len(items),
            total_graph_candidates=0,
            graph_stats=GraphTraversalStats(seeds_used=0, entities_reached=0, chunks_from_graph=0, edges_traversed=[]),
            latency_ms=latency_ms,
            latency_breakdown_ms={"embed": 0, "faiss_search": latency_ms},
        )


class HybridRRFRetriever(BaselineRetriever):
    """
    Hybrid RRF fusion (FAISS + BM25) without graph — memory-safe streaming.
    Reuses the same FAISS candidate pool for both FAISS and BM25 scores.
    """

    def __init__(
        self,
        candidate_pool: int = BM25_CANDIDATE_POOL,
        batch_size: int = BM25_BATCH_SIZE,
        rrf_k: int = 60,
    ):
        super().__init__("HybridRRF")
        self.candidate_pool = candidate_pool
        self.batch_size = batch_size
        self.rrf_k = rrf_k

    def retrieve(self, query: str, top_n: int = 10) -> RetrievalResult:
        t0 = time.perf_counter()

        # 1. Get FAISS top candidate_pool (single search, shared)
        query_vec = embedder.embed_query(query)
        faiss_results = faiss_store.search(query_vec, self.candidate_pool)

        if not faiss_results:
            latency_ms = (time.perf_counter() - t0) * 1000
            return RetrievalResult(
                query=query,
                destination="global",
                items=[],
                total_faiss_candidates=0,
                total_graph_candidates=0,
                graph_stats=GraphTraversalStats(seeds_used=0, entities_reached=0, chunks_from_graph=0, edges_traversed=[]),
                latency_ms=latency_ms,
                latency_breakdown_ms={"fusion": latency_ms},
            )

        # 2. Build FAISS rank map
        faiss_items = {}
        for rank, meta in enumerate(faiss_results):
            chunk_id = meta.get("chunk_id", f"dense_{meta.get('faiss_id', rank)}")
            faiss_items[chunk_id] = (rank, float(meta.get("faiss_score", 0.0)))

        # 3. Load texts for BM25 scoring over same pool
        faiss_ids = [r["faiss_id"] for r in faiss_results]
        id_to_text = faiss_store.batch_load_chunk_texts(faiss_ids)

        # 4. Build tiny BM25 over candidate_pool docs
        tokenized_corpus = []
        valid_faiss_ids = []
        for fid in faiss_ids:
            text = id_to_text.get(fid, "")
            if text:
                tokenized_corpus.append(text.lower().split())
                valid_faiss_ids.append(fid)

        bm25_items = {}
        if tokenized_corpus:
            from rank_bm25 import BM25Okapi
            bm25 = BM25Okapi(tokenized_corpus)
            tokenized_query = query.lower().split()
            scores = bm25.get_scores(tokenized_query)
            for local_rank, fid in enumerate(valid_faiss_ids):
                chunk_id = faiss_results[faiss_ids.index(fid)].get("chunk_id", f"bm25_{fid}")
                bm25_items[chunk_id] = (local_rank, float(scores[local_rank]))

        # 5. RRF fusion
        all_chunk_ids = set(bm25_items.keys()) | set(faiss_items.keys())
        fused_scores = {}

        for chunk_id in all_chunk_ids:
            score = 0.0
            if chunk_id in bm25_items:
                score += 1.0 / (self.rrf_k + bm25_items[chunk_id][0] + 1)
            if chunk_id in faiss_items:
                score += 1.0 / (self.rrf_k + faiss_items[chunk_id][0] + 1)
            fused_scores[chunk_id] = score

        # 6. Sort by fused score, take top-N
        sorted_chunks = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]

        # 7. Build final items
        items = []
        for rank, (chunk_id, fused_score) in enumerate(sorted_chunks):
            meta = None
            source_type = "both"
            faiss_score = 0.0
            bm25_score = 0.0

            if chunk_id in faiss_items:
                for m in faiss_results:
                    if m.get("chunk_id") == chunk_id:
                        meta = m
                        break
                faiss_score = faiss_items[chunk_id][1]
                source_type = "faiss"

            if chunk_id in bm25_items and not meta:
                idx = bm25_items[chunk_id][0]
                if idx < len(faiss_results):
                    meta = faiss_results[idx]
                bm25_score = bm25_items[chunk_id][1]
                if source_type == "faiss":
                    source_type = "both"
                else:
                    source_type = "bm25"

            if meta:
                items.append(EvidenceItem(
                    chunk_id=chunk_id,
                    document_id=meta.get("document_id", "unknown"),
                    faiss_id=meta.get("faiss_id", 0),
                    text_snippet=meta.get("text_snippet", "")[:500],
                    category=meta.get("category", "unknown"),
                    chunk_type=meta.get("chunk_type", "body"),
                    source=meta.get("source", "unknown"),
                    title=meta.get("title"),
                    fused_score=fused_score,
                    faiss_score=faiss_score,
                    graph_score=0.0,
                    source_type=source_type,
                    graph_path=[],
                    graph_entities=[],
                    graph_path_str=None,
                ))

        latency_ms = (time.perf_counter() - t0) * 1000

        return RetrievalResult(
            query=query,
            destination="global",
            items=items,
            total_faiss_candidates=len(faiss_items),
            total_graph_candidates=0,
            graph_stats=GraphTraversalStats(seeds_used=0, entities_reached=0, chunks_from_graph=0, edges_traversed=[]),
            latency_ms=latency_ms,
            latency_breakdown_ms={"fusion": latency_ms},
        )


class GraphOnlyRetriever(BaselineRetriever):
    """
    Graph-only retrieval (Kuzu traversal without FAISS seeding).
    Uses the graph store's public traverse_from_documents with empty seeds.
    """

    def __init__(self):
        super().__init__("GraphOnly")
        graph_store.warm_up()

    def retrieve(self, query: str, top_n: int = 10) -> RetrievalResult:
        t0 = time.perf_counter()

        # Use graph store's public API with empty seed docs (query-only mode)
        results = graph_store.traverse_from_documents([], top_n, query=query)

        # Convert to EvidenceItems
        items = []
        for rank, r in enumerate(results[:top_n]):
            items.append(EvidenceItem(
                chunk_id=r["chunk_id"],
                document_id=r["document_id"],
                faiss_id=r["faiss_id"],
                text_snippet=r.get("text_snippet", "")[:500],
                category=r["category"],
                chunk_type=r["chunk_type"],
                source=r["source_doc"],
                title=r.get("title"),
                fused_score=r.get("graph_score", 0.5),
                faiss_score=0.0,
                graph_score=r.get("graph_score", 0.5),
                source_type="graph",
                graph_path=r.get("graph_path", []),
                graph_entities=r.get("graph_entities", []),
                graph_path_str=r.get("graph_path_str"),
            ))

        latency_ms = (time.perf_counter() - t0) * 1000

        # Extract entities reached from results (graph_entities is list of dicts, extract names)
        entity_names = set()
        for r in results:
            for ent in r.get("graph_entities", []):
                if isinstance(ent, dict):
                    entity_names.add(ent.get("name", ""))
                else:
                    entity_names.add(str(ent))
        entities_reached = len(entity_names)

        return RetrievalResult(
            query=query,
            destination="global",
            items=items,
            total_faiss_candidates=0,
            total_graph_candidates=len(results),
            graph_stats=GraphTraversalStats(seeds_used=0, entities_reached=entities_reached, chunks_from_graph=len(results), edges_traversed=[]),
            latency_ms=latency_ms,
            latency_breakdown_ms={"graph_traversal": latency_ms},
        )


class MedGraphRAGRetriever(BaselineRetriever):
    """
    Full MedGraphRAG retriever (reference implementation).
    """

    def __init__(self):
        super().__init__("MedGraphRAG")
        self.service = HybridRetrievalService()

    def retrieve(self, query: str, top_n: int = 10) -> RetrievalResult:
        req = RetrievalRequest(query=query, destination="global", top_n=top_n)
        return self.service.retrieve(req)


def run_baseline_comparison(
    queries: Optional[List[str]] = None,
    top_n: int = 10,
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Run all baseline retrievers on the same queries and compare results.
    Instantiates retrievers lazily per query to avoid memory buildup.
    """
    if queries is None:
        queries = BASELINE_QUERIES

    retriever_classes = [
        (BM25Retriever, {}),
        (DenseVectorRetriever, {}),
        (HybridRRFRetriever, {}),
        (GraphOnlyRetriever, {}),
        (MedGraphRAGRetriever, {}),
    ]

    all_results = {}

    for retriever_cls, kwargs in retriever_classes:
        logger.info("Running baseline: %s", retriever_cls.__name__)
        retriever_results = {}

        for query in queries:
            try:
                retriever = retriever_cls(**kwargs)
                result = retriever.retrieve(query, top_n=top_n)
                retriever_results[query] = {
                    "latency_ms": result.latency_ms,
                    "num_items": len(result.items),
                    "items": [
                        {
                            "rank": i + 1,
                            "chunk_id": item.chunk_id,
                            "document_id": item.document_id,
                            "fused_score": item.fused_score,
                            "source_type": item.source_type,
                            "category": item.category,
                        }
                        for i, item in enumerate(result.items)
                    ],
                    "graph_stats": result.graph_stats,
                }
                # Explicit cleanup to avoid memory drift between queries
                del retriever
                gc.collect()
            except Exception as e:
                logger.error("Error in %s for query '%s': %s", retriever_cls.__name__, query, e)
                retriever_results[query] = {"error": str(e)}

        all_results[retriever_cls.__name__] = retriever_results

    # Compute summary metrics
    summary = {}
    for retriever_name, results in all_results.items():
        latencies = []
        item_counts = []
        graph_reached = []
        graph_chunks = []

        for query, result in results.items():
            if "error" not in result:
                latencies.append(result["latency_ms"])
                item_counts.append(result["num_items"])
                gs = result.get("graph_stats")
                graph_reached.append(gs.entities_reached if gs else 0)
                graph_chunks.append(gs.chunks_from_graph if gs else 0)

        summary[retriever_name] = {
            "avg_latency_ms": np.mean(latencies) if latencies else 0,
            "avg_items": np.mean(item_counts) if item_counts else 0,
            "avg_entities_reached": np.mean(graph_reached) if graph_reached else 0,
            "avg_graph_chunks": np.mean(graph_chunks) if graph_chunks else 0,
            "queries_successful": len(latencies),
            "queries_total": len(queries),
        }

    final_report = {
        "queries": queries,
        "top_n": top_n,
        "results": all_results,
        "summary": summary,
        "timestamp": time.time(),
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(final_report, f, indent=2, default=str)
        logger.info("Baseline comparison saved to: %s", output_path)

    return final_report


def print_summary(report: Dict[str, Any]) -> None:
    """Print a formatted summary of baseline comparison results."""
    print("\n" + "=" * 80)
    print("BASELINE RETRIEVAL COMPARISON SUMMARY")
    print("=" * 80)
    print(f"Queries: {len(report['queries'])} | Top-N: {report['top_n']}")
    print("-" * 80)

    summary = report["summary"]
    for name, metrics in summary.items():
        print(f"\n{name}:")
        print(f"  Avg Latency: {metrics['avg_latency_ms']:.1f} ms")
        print(f"  Avg Items: {metrics['avg_items']:.1f}")
        print(f"  Avg Entities Reached: {metrics['avg_entities_reached']:.1f}")
        print(f"  Avg Graph Chunks: {metrics['avg_graph_chunks']:.1f}")
        print(f"  Success Rate: {metrics['queries_successful']}/{metrics['queries_total']}")

    print("=" * 80)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run baseline retrieval comparison")
    parser.add_argument("--output", "-o", type=str, help="Output JSON path")
    parser.add_argument("--top-n", type=int, default=10, help="Top N results per query")
    parser.add_argument("--queries", "-q", nargs="+", help="Custom queries to evaluate")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    output_path = Path(args.output) if args.output else None

    report = run_baseline_comparison(
        queries=args.queries,
        top_n=args.top_n,
        output_path=output_path,
    )

    print_summary(report)