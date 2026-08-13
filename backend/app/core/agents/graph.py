"""
MedGraphRAG Backend — Agent Graph Compilation
================================================
Compiles the multi-agent LangGraph StateGraph topology:

  START -> router -> conditional {
                       'medical_query'   -> query_agent,
                       'knowledge_graph' -> knowledge_agent,
                       'report'          -> report_agent,
                       'out_of_scope'    -> out_of_scope
                     } -> finalize -> END
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.core.agents.nodes import (
    finalize_node,
    knowledge_agent_node,
    out_of_scope_node,
    query_agent_node,
    report_agent_node,
    router_node,
)
from app.core.agents.state import MedGraphState

logger = logging.getLogger(__name__)


def route_decision(state: MedGraphState) -> str:
    """Extract route string from state for conditional edge routing."""
    return state.get("route", "medical_query")


def build_medgraph_graph(checkpointer: bool = True):
    """
    Build and compile the MedGraphRAG LangGraph StateGraph.

    Parameters
    ----------
    checkpointer : bool
        If True, attaches MemorySaver checkpointer for thread session tracing.

    Returns
    -------
    Compiled StateGraph instance.
    """
    builder = StateGraph(MedGraphState)

    # ── Add Nodes ────────────────────────────────────────────────────────────
    builder.add_node("router", router_node)
    builder.add_node("query_agent", query_agent_node)
    builder.add_node("knowledge_agent", knowledge_agent_node)
    builder.add_node("report_agent", report_agent_node)
    builder.add_node("out_of_scope", out_of_scope_node)
    builder.add_node("finalize", finalize_node)

    # ── Add Edges ────────────────────────────────────────────────────────────
    builder.add_edge(START, "router")
    builder.add_conditional_edges(
        "router",
        route_decision,
        {
            "medical_query": "query_agent",
            "knowledge_graph": "knowledge_agent",
            "report": "report_agent",
            "out_of_scope": "out_of_scope",
        },
    )

    builder.add_edge("query_agent", "finalize")
    builder.add_edge("knowledge_agent", "finalize")
    builder.add_edge("report_agent", "finalize")
    builder.add_edge("out_of_scope", "finalize")
    builder.add_edge("finalize", END)

    saver = MemorySaver() if checkpointer else None
    compiled_graph = builder.compile(checkpointer=saver)

    logger.info("MedGraphRAG LangGraph StateGraph compiled successfully (checkpointer=%s).", checkpointer)
    return compiled_graph
