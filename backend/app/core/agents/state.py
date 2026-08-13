"""
MedGraphRAG Backend — Agent State Schema
==========================================
MedGraphState TypedDict representing the execution state passed across LangGraph nodes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from app.core.retrieval.schemas import RetrievalResult
from app.core.verification.schemas import VerifiedAnswerResult


class MedGraphState(TypedDict, total=False):
    """
    MedGraphState TypedDict for multi-agent LangGraph orchestration.
    """

    query: str
    user_id: Optional[str]
    destination: str
    report_payload: Optional[Dict[str, Any]]
    route: str  # 'medical_query' | 'knowledge_graph' | 'report' | 'out_of_scope'
    retrieval_result: Optional[RetrievalResult]
    verified_result: Optional[VerifiedAnswerResult]
    final_response: Dict[str, Any]
    latency_ms: Dict[str, float]
    error: Optional[str]
