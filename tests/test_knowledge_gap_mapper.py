"""
Unit Tests for Epistemic Knowledge-Gap Mapper (F2)
===================================================
DO NOT RUN (Static compile verification only per R1).
Tests pure rule-based logic in app.core.guardrail.knowledge_gaps.
"""

import pytest
from app.core.guardrail.knowledge_gaps import map_knowledge_gaps
from app.core.guardrail.schemas import KnowledgeGap


def test_corpus_retrieval_gap_low_fused_score():
    """G1: Top fused score < 0.02 triggers corpus_retrieval gap with reformulations."""
    query = "What is the recommended dosage for investigational kinase inhibitor ABX-492?"
    retrieved_items = [
        {"chunk_id": "chunk_001", "document_id": "doc_general", "fused_score": 0.009}
    ]

    gaps = map_knowledge_gaps(
        query=query,
        retrieved_items=retrieved_items,
        phi=0.40,
        answer_status="refusal",
    )

    g1_gaps = [g for g in gaps if g.gap_type == "corpus_retrieval"]
    assert len(g1_gaps) >= 1
    gap = g1_gaps[0]
    assert "below relevance threshold" in gap.detail
    assert len(gap.suggested_queries) >= 1
    assert len(gap.suggested_sources) >= 1


def test_graph_coverage_gap_neutral_check():
    """G2: Neutral graph check triggers graph_coverage gap."""
    query = "Does warfarin interact with St Johns Wort in atrial fibrillation?"
    retrieved_items = [
        {"chunk_id": "chunk_002", "document_id": "doc_warfarin", "fused_score": 0.08}
    ]
    graph_checks = {
        "verdict": "neutral",
        "reason": "No direct graph assertion linking warfarin to herbal supplement via INTERACTS_WITH",
    }

    gaps = map_knowledge_gaps(
        query=query,
        retrieved_items=retrieved_items,
        graph_checks=graph_checks,
        phi=0.60,
        answer_status="uncertain",
    )

    g2_gaps = [g for g in gaps if g.gap_type == "graph_coverage"]
    assert len(g2_gaps) >= 1
    gap = g2_gaps[0]
    assert "graph" in gap.detail.lower()
    assert any("UMLS" in s or "DrugBank" in s for s in gap.suggested_sources)


def test_evidence_faithfulness_gap_low_phi():
    """G3: Low faithfulness score (phi < 0.50) triggers evidence_faithfulness gap."""
    query = "Can metformin be safely prescribed in end-stage renal failure with eGFR < 15?"
    retrieved_items = [
        {"chunk_id": "chunk_003", "document_id": "doc_metformin_guidelines", "fused_score": 0.12}
    ]

    gaps = map_knowledge_gaps(
        query=query,
        retrieved_items=retrieved_items,
        phi=0.32,
        answer_status="refusal",
    )

    g3_gaps = [g for g in gaps if g.gap_type == "evidence_faithfulness"]
    assert len(g3_gaps) >= 1
    gap = g3_gaps[0]
    assert "0.32" in gap.detail
    assert any("doc_metformin_guidelines" in sq for sq in gap.suggested_queries)


def test_verified_high_confidence_produces_no_gaps():
    """Verified, high-faithfulness query execution produces zero knowledge gaps."""
    query = "warfarin INR monitoring guidelines"
    retrieved_items = [
        {"chunk_id": "chunk_004", "document_id": "doc_inr_guideline", "fused_score": 0.22}
    ]

    gaps = map_knowledge_gaps(
        query=query,
        retrieved_items=retrieved_items,
        phi=0.92,
        answer_status="verified",
    )

    assert len(gaps) == 0


def test_fail_open_on_none_input():
    """Fail-open behavior safely handles None and missing arguments."""
    assert map_knowledge_gaps(query="") == []
    assert map_knowledge_gaps(query="test", retrieved_items=None) == []
