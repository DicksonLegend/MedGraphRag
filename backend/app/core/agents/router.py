"""
MedGraphRAG Backend — Router Agent
===================================
Classifies incoming user requests into intent routes:
  - 'medical_query'   : Standard RAG pipeline
  - 'knowledge_graph' : Graph-first RAG pipeline (relational/entity queries)
  - 'report'          : Diagnostic report interpretation (Step 10 stub)
  - 'out_of_scope'    : Non-medical smalltalk or out-of-scope requests

Rule-First (CPU, < 5 ms):
  1. Checks report_payload presence -> 'report'
  2. Out-of-scope keyword matching -> 'out_of_scope'
  3. Relational phrasing keyword matching -> 'knowledge_graph'
  4. Medical domain keyword matching -> 'medical_query'

LLM Fallback (CPU/GPU singleton):
  Used only when rule-first classification is inconclusive.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, Optional, Tuple

from app.config import settings
from app.core.llm.llm_loader import generate_chat

logger = logging.getLogger(__name__)


def classify_intent(
    query: str,
    report_payload: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str, float]:
    """
    Classify query intent into a target route.

    Parameters
    ----------
    query : str
        User natural language query.
    report_payload : dict, optional
        Optional diagnostic lab report payload.

    Returns
    -------
    tuple of (route: str, mechanism: str, latency_ms: float)
    """
    t0 = time.perf_counter()
    query_lower = query.strip().lower()

    # ── Rule 1: Report payload present ───────────────────────────────────────
    if report_payload and isinstance(report_payload, dict) and len(report_payload) > 0:
        latency_ms = (time.perf_counter() - t0) * 1000
        logger.info("Router decision: route=report, mechanism=rule_first, latency=%.2f ms", latency_ms)
        return "report", "rule_first", latency_ms

    # ── Rule 2: Out of scope check ────────────────────────────────────────────
    for kw in settings.router_out_of_scope_keywords:
        if kw in query_lower:
            latency_ms = (time.perf_counter() - t0) * 1000
            logger.info("Router decision: route=out_of_scope, mechanism=rule_first, latency=%.2f ms", latency_ms)
            return "out_of_scope", "rule_first", latency_ms

    # ── Rule 3: Relational / Graph phrasing check ────────────────────────────
    for kw in settings.router_relational_keywords:
        if kw in query_lower:
            latency_ms = (time.perf_counter() - t0) * 1000
            logger.info("Router decision: route=knowledge_graph, mechanism=rule_first, latency=%.2f ms", latency_ms)
            return "knowledge_graph", "rule_first", latency_ms

    # ── Rule 4: General medical terms check ──────────────────────────────────
    medical_keywords = [
        "guideline", "treatment", "diagnosis", "symptom", "dosage", "inr",
        "hemoglobin", "troponin", "metformin", "aspirin", "dvt", "sepsis",
        "potassium", "hyperkalemia", "beta blocker", "ace inhibitor", "hypertension",
        "disease", "drug", "blood pressure", "anemia", "cardiac", "infarction"
    ]
    if any(kw in query_lower for kw in medical_keywords):
        latency_ms = (time.perf_counter() - t0) * 1000
        logger.info("Router decision: route=medical_query, mechanism=rule_first, latency=%.2f ms", latency_ms)
        return "medical_query", "rule_first", latency_ms

    # ── LLM Fallback (if enabled) ────────────────────────────────────────────
    if settings.router_llm_fallback_enabled:
        try:
            prompt = settings.router_llm_classification_prompt.replace("{query}", query)
            messages = [{"role": "user", "content": prompt}]
            llm_res = generate_chat(messages=messages, max_tokens=20, temperature=0.0)
            raw_route = llm_res.get("text", "").strip().lower()

            for valid_route in ("knowledge_graph", "medical_query", "report", "out_of_scope"):
                if valid_route in raw_route:
                    if valid_route == "report" and not (report_payload and len(report_payload) > 0):
                        valid_route = "medical_query"
                    latency_ms = (time.perf_counter() - t0) * 1000
                    logger.info("Router decision: route=%s, mechanism=llm_fallback, latency=%.2f ms", valid_route, latency_ms)
                    return valid_route, "llm_fallback", latency_ms
        except Exception as exc:
            logger.warning("Router LLM fallback failed: %s. Defaulting to medical_query.", exc)

    # Default fallback: medical_query
    latency_ms = (time.perf_counter() - t0) * 1000
    logger.info("Router decision: route=medical_query, mechanism=rule_default, latency=%.2f ms", latency_ms)
    return "medical_query", "rule_default", latency_ms
