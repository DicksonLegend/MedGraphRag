"""
MedGraphRAG Backend — Stage G: Report Interpretation Service
=============================================================
Orchestrates Stages A through F for diagnostic lab report processing:
  Stage A: Multi-format parsing (PDF, Image, XLSX, CSV)
  Stage B: Lab value extraction (regex rules + LLM fallback)
  Stage C: Normalization & Kuzu ontology mapping
  Stage D: Range assessment (normal / low / high / critical)
  Stage E: Graph-backed plain-language explanation + strict provenance
  Stage F: Isolated AES-256-GCM encrypted private storage
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.report.assessor import assess_lab_values
from app.core.report.explainer import generate_explanations
from app.core.report.extractor import extract_lab_values
from app.core.report.normalizer import normalize_lab_values
from app.core.report.parser import parse_report_bytes
from app.core.report.schemas import ReportResult
from app.core.report.store import store_private_report

logger = logging.getLogger(__name__)

CRITICAL_ESCALATION_TEXT = (
    "⚠️ CRITICAL VALUE DETECTED — seek urgent medical care immediately!\n"
    "One or more laboratory results fall in a critical range requiring immediate clinical evaluation."
)


class ReportInterpretationService:
    """Service orchestrating diagnostic report analysis, safety assessment, and private storage."""

    def process_report(
        self,
        file_bytes: bytes,
        filename: str,
        user_id: str = "default_user",
        destination: str = "private",
    ) -> ReportResult:
        """
        Process diagnostic report file bytes across Stages A-F.

        Parameters
        ----------
        file_bytes : bytes
        filename : str
        user_id : str
        destination : str

        Returns
        -------
        ReportResult
        """
        t0 = time.perf_counter()
        logger.info("ReportInterpretationService: Processing %s for user %s", filename, user_id)

        # Stage A: Multi-format parsing
        parsed = parse_report_bytes(file_bytes=file_bytes, filename=filename)

        # Stage B: Lab value extraction
        lab_vals = extract_lab_values(parsed)

        # Stage C: Normalization & Ontology mapping
        normalized_vals = normalize_lab_values(lab_vals)

        # Stage D: Range assessment
        assessments, critical_flag = assess_lab_values(normalized_vals)

        # Stage E: Provenanced explanation generation
        explanations = generate_explanations(assessments)

        # Stage F: Isolated AES-256-GCM encrypted private storage
        private_store_path = store_private_report(
            user_id=user_id,
            raw_text=parsed.raw_text,
            lab_values=lab_vals,
            assessments=assessments,
            explanations=explanations,
        )

        total_ms = (time.perf_counter() - t0) * 1000

        # Build combined provenance list
        combined_provenance: List[str] = []
        for exp in explanations:
            combined_provenance.extend(exp.provenance)
        combined_provenance = list(dict.fromkeys(combined_provenance))

        parsed_summary = f"Parsed {parsed.format.upper()} report ({len(lab_vals)} lab values extracted)."
        escalation_text = CRITICAL_ESCALATION_TEXT if critical_flag else None

        result = ReportResult(
            user_id=user_id,
            parsed_summary=parsed_summary,
            lab_values=lab_vals,
            assessments=assessments,
            explanations=explanations,
            critical_flag=critical_flag,
            escalation_text=escalation_text,
            private_store_path=str(private_store_path),
            provenance=combined_provenance,
            disclaimer="This is information, not medical advice — consult your physician.",
            processing_latency_ms=round(total_ms, 2),
        )

        logger.info(
            "ReportInterpretationService complete for %s (user=%s, critical=%s, latency=%.2f ms)",
            filename, user_id, critical_flag, total_ms
        )
        return result
