"""
MedGraphRAG Backend — Feature 3: Evidence Coverage Map
========================================================
Decomposes complex medical queries into 2-5 atomic sub-questions,
retrieves hybrid evidence per sub-question, classifies coverage into
{strong, partial, none}, and generates suggested query rephrases for
low-coverage topics to turn refusals into informative user guidance.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.features.schemas import (
    CoverageClass,
    CoverageMap,
    SubQuestionCoverage,
)
from app.core.llm.llm_loader import get_llm
from app.core.retrieval.schemas import RetrievalRequest
from app.core.retrieval.service import HybridRetrievalService

logger = logging.getLogger(__name__)


SUBQUESTION_DECOMPOSITION_PROMPT = (
    "You are a medical query parser. Decompose the following medical query into 2 to 5 "
    "focused, atomic sub-questions that cover the key clinical components of the inquiry.\n\n"
    "Respond ONLY with a valid JSON object in this exact format:\n"
    '{{"sub_questions": ["sub-question 1", "sub-question 2", ...]}}\n\n'
    "Do NOT include any preamble, commentary, or markdown formatting outside the JSON.\n\n"
    "QUERY: {query}"
)


class CoverageMapService:
    """Service for query decomposition, evidence coverage assessment, and query suggestion."""

    def __init__(self):
        self.retrieval_service = HybridRetrievalService()

    def evaluate_coverage(self, query: str) -> CoverageMap:
        """
        Decompose query and evaluate evidence coverage across sub-questions.

        Parameters
        ----------
        query : str
            User's natural language medical query.

        Returns
        -------
        CoverageMap
        """
        logger.info("CoverageMapService: Evaluating evidence coverage for query: '%s'", query)

        # 1. Decompose query into sub-questions via LLM
        sub_questions = self._decompose_query(query)
        logger.info("Decomposed into %d sub-questions: %s", len(sub_questions), sub_questions)

        sub_coverages: List[SubQuestionCoverage] = []
        all_rephrases: List[str] = []

        # 2. Evaluate retrieval coverage per sub-question
        for sub_q in sub_questions:
            cov = self._evaluate_single_subquestion(sub_q)
            sub_coverages.append(cov)
            if cov.suggested_rephrase:
                all_rephrases.append(cov.suggested_rephrase)

        # 3. Compute overall coverage tier
        strong_cnt = sum(1 for c in sub_coverages if c.coverage_class == CoverageClass.STRONG)
        partial_cnt = sum(1 for c in sub_coverages if c.coverage_class == CoverageClass.PARTIAL)
        none_cnt = sum(1 for c in sub_coverages if c.coverage_class == CoverageClass.NONE)

        if none_cnt == len(sub_coverages):
            overall = CoverageClass.NONE
        elif strong_cnt == len(sub_coverages):
            overall = CoverageClass.STRONG
        elif strong_cnt >= 1:
            overall = CoverageClass.STRONG if none_cnt == 0 else CoverageClass.PARTIAL
        else:
            overall = CoverageClass.PARTIAL if partial_cnt > 0 else CoverageClass.NONE

        return CoverageMap(
            query=query,
            sub_questions=sub_coverages,
            overall_coverage=overall,
            strong_count=strong_cnt,
            partial_count=partial_cnt,
            none_count=none_cnt,
            suggested_rephrases=all_rephrases,
            disclaimer="This is information, not medical advice — consult your physician.",
            disclaimer_present=True,
        )

    def _decompose_query(self, query: str) -> List[str]:
        """Decompose query into 2-5 sub-questions using the LLM singleton."""
        prompt = SUBQUESTION_DECOMPOSITION_PROMPT.format(query=query)

        raw_response = ""
        try:
            llm = get_llm()
            messages = [
                {"role": "system", "content": "You are a clinical query parser that outputs only valid JSON."},
                {"role": "user", "content": prompt},
            ]
            res = llm.create_chat_completion(
                messages=messages,
                max_tokens=300,
                temperature=0.1,
            )
            raw_response = res["choices"][0]["message"]["content"].strip()
            sub_questions = self._parse_json_subquestions(raw_response)
            if sub_questions and len(sub_questions) >= 2:
                return sub_questions[:5]
        except Exception as e:
            logger.warning("LLM sub-question decomposition failed: %s (Raw: '%s')", e, raw_response)

        # Fallback heuristic decomposition if LLM JSON parsing failed
        return self._heuristic_decomposition(query)

    def _parse_json_subquestions(self, text: str) -> List[str]:
        """Parse sub-questions JSON from model output with regex extraction fallback."""
        # 1. Direct JSON parse
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "sub_questions" in data and isinstance(data["sub_questions"], list):
                return [str(q).strip() for q in data["sub_questions"] if str(q).strip()]
        except Exception:
            pass

        # 2. Extract JSON markdown block ```json ... ```
        block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if block_match:
            try:
                data = json.loads(block_match.group(1))
                if isinstance(data, dict) and "sub_questions" in data and isinstance(data["sub_questions"], list):
                    return [str(q).strip() for q in data["sub_questions"] if str(q).strip()]
            except Exception:
                pass

        # 3. Regex line matching for array items: "..."
        lines = re.findall(r'"([^"\n\r]{10,120})"', text)
        clean_lines = [l.strip() for l in lines if not l.lower().startswith("sub_questions") and len(l) > 10]
        if len(clean_lines) >= 2:
            return clean_lines[:5]

        return []

    def _heuristic_decomposition(self, query: str) -> List[str]:
        """Split query by clauses/keywords into 2-3 structured sub-questions."""
        q_clean = query.strip()
        clauses = re.split(r",|;|\band\b|\bwith\b|\bfor\b", q_clean, flags=re.IGNORECASE)
        clauses = [c.strip() for c in clauses if len(c.strip()) > 3]

        if len(clauses) >= 2:
            return [
                f"What are the clinical guidelines and mechanisms regarding {clauses[0]}?",
                f"How does {clauses[1]} affect clinical outcomes and management?",
            ]

        # Standard 2-part expansion
        return [
            f"What is the clinical definition and diagnostic criteria for {q_clean}?",
            f"What are the evidence-based management and monitoring recommendations for {q_clean}?",
        ]

    def _evaluate_single_subquestion(self, sub_q: str) -> SubQuestionCoverage:
        """Retrieve hybrid evidence and evaluate coverage metrics for a sub-question."""
        top_fused_score = 0.0
        distinct_doc_count = 0
        evidence_count = 0
        top_citations = []

        try:
            req = RetrievalRequest(query=sub_q, top_n=10)
            ret_res = self.retrieval_service.retrieve(req)
            evidence_count = len(ret_res.items)

            if evidence_count > 0:
                top_fused_score = max(item.fused_score for item in ret_res.items)
                distinct_docs = set(item.document_id for item in ret_res.items)
                distinct_doc_count = len(distinct_docs)
                top_citations = [f"{item.source} ({item.document_id}): {getattr(item, 'text_snippet', getattr(item, 'snippet', ''))[:120]}..." for item in ret_res.items[:2]]
        except Exception as e:
            logger.warning("Retrieval failed for sub-question '%s': %s", sub_q, e)

        # Calibrate coverage classification based on MedGraphRAG RRF scoring
        if top_fused_score >= 0.12 and distinct_doc_count >= 2:
            cov_class = CoverageClass.STRONG
            rephrase = None
        elif (top_fused_score >= 0.03 and top_fused_score < 0.12) or (top_fused_score >= 0.12 and distinct_doc_count == 1):
            cov_class = CoverageClass.PARTIAL
            rephrase = self._generate_suggested_rephrase(sub_q)
        else:
            cov_class = CoverageClass.NONE
            rephrase = self._generate_suggested_rephrase(sub_q)

        return SubQuestionCoverage(
            sub_question=sub_q,
            coverage_class=cov_class,
            top_fused_score=round(top_fused_score, 4),
            distinct_doc_count=distinct_doc_count,
            evidence_count=evidence_count,
            top_citations=top_citations,
            suggested_rephrase=rephrase,
        )

    def _generate_suggested_rephrase(self, sub_q: str) -> str:
        """Generate a focused rephrase suggestion for low-coverage sub-questions."""
        clean_q = re.sub(r"^(what are|what is|how does|can you tell me about)\s+", "", sub_q, flags=re.IGNORECASE).strip(" ?.")
        return f"Try searching with standard medical nomenclature: '{clean_q} diagnosis treatment guidelines'"
