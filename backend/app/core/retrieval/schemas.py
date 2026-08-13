"""
MedGraphRAG Backend — Retrieval Schemas
=========================================
Typed data models for retrieval inputs and outputs.
All models use Pydantic v2.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Evidence item — a single retrieved chunk with full provenance
# ---------------------------------------------------------------------------

class EvidenceItem(BaseModel):
    """
    A single retrieved chunk, enriched with provenance and scoring metadata.
    """

    # ── Identity ─────────────────────────────────────────────────────────────
    chunk_id: str = Field(
        description="Unique chunk identifier (aligns with sidecar + graph)."
    )
    document_id: str = Field(
        description="Parent document identifier."
    )
    faiss_id: int = Field(
        description="FAISS integer index used for this chunk."
    )

    # ── Category & type ───────────────────────────────────────────────────────
    category: str = Field(
        description="Document category (guideline, drug, lab_reference, …)."
    )
    chunk_type: str = Field(
        description="Chunk type (prose, structured_row, table_row, …)."
    )
    source: str = Field(
        description="Source dataset folder."
    )
    title: Optional[str] = Field(
        default=None,
        description="Document title if available.",
    )

    # ── Text snippet ─────────────────────────────────────────────────────────
    text_snippet: str = Field(
        description="Truncated text from the chunk (≤ config.text_snippet_max_chars)."
    )

    # ── Scoring ───────────────────────────────────────────────────────────────
    faiss_score: float = Field(
        description="Cosine similarity score from FAISS (0–1 after L2-normalisation)."
    )
    graph_score: float = Field(
        default=0.0,
        description=(
            "Normalised graph strength score (0–1). 0 if not reached by graph traversal."
        ),
    )
    fused_score: float = Field(
        description="Reciprocal Rank Fusion score after FAISS + graph fusion."
    )
    graph_boost_applied: bool = Field(
        default=False,
        description="True if a high-trust graph edge boosted this item's fused_score.",
    )

    # ── Graph provenance ─────────────────────────────────────────────────────
    graph_path: List[str] = Field(
        default_factory=list,
        description=(
            "Sequence of edge labels traversed to reach this chunk from a seed "
            "(e.g., ['DOCUMENT_MENTIONS', 'HAS_CHUNK']). Empty if FAISS-only."
        ),
    )
    graph_entities: List[Dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Entity nodes encountered during graph traversal "
            "(keys: label, id, name). Empty if FAISS-only."
        ),
    )
    graph_path_str: Optional[str] = Field(
        default=None,
        description="Formatted human-readable graph path string (e.g. 'LabTest(X) -> Disease(Y) -> Chunk(Z)').",
    )

    # ── Retrieval source ─────────────────────────────────────────────────────
    source_type: Literal["faiss", "graph", "both"] = Field(
        description=(
            "'faiss' — found only by vector search. "
            "'graph' — found only by graph traversal. "
            "'both' — found by both (best evidence)."
        ),
    )


# ---------------------------------------------------------------------------
# Retrieval request / result
# ---------------------------------------------------------------------------

class RetrievalRequest(BaseModel):
    """Input to HybridRetrievalService.retrieve()."""

    query: str = Field(
        description="The natural-language query string."
    )
    top_n: Optional[int] = Field(
        default=None,
        description=(
            "Override the global retrieval_top_n setting. "
            "Defaults to settings.retrieval_top_n if None."
        ),
    )
    destination: str = Field(
        default="global",
        description=(
            "Index destination to query. Default 'global'. "
            "Pass a user_id to route to a private index (future). "
            "Parameterized here so the same code later serves per-user private indexes."
        ),
    )
    category_filter: Optional[List[str]] = Field(
        default=None,
        description=(
            "Optional list of category names to restrict retrieval. "
            "If None, all categories are retrieved subject to balancing caps."
        ),
    )


class GraphTraversalStats(BaseModel):
    """Diagnostic stats from the graph traversal leg."""

    seeds_used: int = Field(description="Number of seed document_ids used.")
    entities_reached: int = Field(description="Number of distinct entities reached via graph.")
    chunks_from_graph: int = Field(description="Number of graph-only evidence items.")
    edges_traversed: List[str] = Field(
        default_factory=list,
        description="Distinct edge types traversed during this query.",
    )


class RetrievalResult(BaseModel):
    """Full output of HybridRetrievalService.retrieve()."""

    query: str = Field(description="The original query string.")
    destination: str = Field(description="Index destination that was queried.")
    items: List[EvidenceItem] = Field(
        description="Ranked list of EvidenceItems, best first."
    )
    total_faiss_candidates: int = Field(
        description="Number of raw FAISS hits before category balancing."
    )
    total_graph_candidates: int = Field(
        description="Number of graph-sourced candidates before fusion."
    )
    graph_stats: GraphTraversalStats = Field(
        description="Graph traversal diagnostics."
    )
    latency_ms: float = Field(
        description="Total retrieval wall-clock time in milliseconds."
    )
    latency_breakdown_ms: Dict[str, float] = Field(
        default_factory=dict,
        description="Per-stage latency breakdown (embed, faiss, graph, fuse).",
    )
