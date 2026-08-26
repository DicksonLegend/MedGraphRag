"""
MedGraphRAG Backend — Agent Orchestrator Service
==================================================
Unified service entrypoint for multi-agent LangGraph orchestration.

Provides:
  AgentOrchestrator.answer(
      query: str,
      user_id: Optional[str] = None,
      destination: str = "global",
      report_payload: Optional[Dict[str, Any]] = None,
  ) -> Dict[str, Any]
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.core.agents.graph import build_medgraph_graph

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """
    Unified multi-agent orchestrator service wrapping the LangGraph StateGraph pipeline.
    """

    def __init__(self, use_checkpointer: bool = True) -> None:
        self.graph = build_medgraph_graph(checkpointer=use_checkpointer)

    def answer(
        self,
        query: str,
        user_id: Optional[str] = None,
        destination: str = "global",
        report_payload: Optional[Dict[str, Any]] = None,
        attached_scan_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute full multi-agent LangGraph workflow for a given query, report payload, or scan attachment.

        Parameters
        ----------
        query : str
            Natural language medical question or prompt.
        user_id : str, optional
            Optional user ID for private index destination routing.
        destination : str
            Target index destination (default 'global' or 'private_store/<user_id>').
        report_payload : dict, optional
            Optional lab report payload dict.
        attached_scan_id : str, optional
            Optional scan image_id attached to query for multimodal context.

        Returns
        -------
        dict containing formatted final_response:
          {route, answer_text, answer_status, confidence_tier, final_confidence,
           citations, graph_paths, disclaimer_present, retry_count, latency_breakdown}
        """
        # Resolve private destination if user_id is provided
        if user_id and destination == "global":
            destination = f"private_store/{user_id}"

        # Fetch scan context if attached_scan_id provided
        attached_scan_context = None
        if attached_scan_id and user_id:
            try:
                from app.multimodal.service import MultimodalService
                svc = MultimodalService()
                attached_scan_context = svc.get_scan_context(user_id=user_id, image_id=attached_scan_id)
                if attached_scan_context:
                    logger.info("Attached scan context loaded for scan %s (user %s)", attached_scan_id, user_id)
            except Exception as e:
                logger.warning("Failed loading attached scan context for %s: %s", attached_scan_id, e)

        initial_state = {
            "query": query,
            "user_id": user_id,
            "destination": destination,
            "report_payload": report_payload,
            "attached_scan_id": attached_scan_id,
            "attached_scan_context": attached_scan_context,
            "latency_ms": {},
        }

        import uuid
        thread_id = f"{user_id}_{uuid.uuid4().hex[:8]}" if user_id else f"thread_{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": thread_id}}

        logger.info("AgentOrchestrator invoking graph for query %r (destination=%s, user_id=%s, scan=%s)", query, destination, user_id, attached_scan_id)
        final_state = self.graph.invoke(initial_state, config=config)

        return final_state.get("final_response", {})
