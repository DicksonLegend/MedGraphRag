"""
MedGraphRAG Backend — Report Interpretation Schemas
===================================================
Pydantic data models for diagnostic report parsing, lab value extraction,
range assessment, graph-backed explanations with provenance, and private storage.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ParsedReport(BaseModel):
    """Output of Stage A multi-format parsing."""
    raw_text: str = Field(..., description="Full extracted text content")
    text_blocks: List[str] = Field(default_factory=list, description="Text blocks or paragraphs")
    tables: List[List[List[str]]] = Field(default_factory=list, description="Extracted table rows")
    format: str = Field(..., description="Source format: pdf | image | xlsx | csv")
    raw_bytes_hash: str = Field(..., description="SHA-256 hash of original file bytes")
    images_meta: List[Dict[str, Any]] = Field(default_factory=list, description="Metadata for image/OCR steps")
    needs_review: bool = Field(False, description="Flagged true if parsing/OCR had low confidence")


class LabValue(BaseModel):
    """Output of Stage B lab value extraction."""
    raw_text: str = Field(..., description="Full line or row text from which value was extracted")
    test_name_raw: str = Field(..., description="Raw un-altered test name from report")
    value_raw: float = Field(..., description="Raw extracted numeric value")
    value_raw_str: str = Field(..., description="Byte-identical raw string representation")
    unit_raw: str = Field(..., description="Raw un-altered unit string")
    reference_range_raw: str = Field("", description="Raw reference range string from report if present")
    patient_context: Dict[str, Any] = Field(default_factory=dict, description="Age, sex, or clinical context")
    source_page: Optional[int] = Field(None, description="Page number (1-indexed)")
    source_row: Optional[int] = Field(None, description="Row or line number")
    extraction_confidence: float = Field(1.0, description="Confidence score 0.0 to 1.0")
    needs_review: bool = Field(False, description="True if extraction confidence < threshold")


class NormalizedLabValue(BaseModel):
    """Output of Stage C normalization and ontology mapping."""
    lab_value: LabValue
    canonical_test_name: str = Field(..., description="Mapped canonical disease/lab test name")
    loinc_code: Optional[str] = Field(None, description="LOINC code if available")
    normalized_value: float = Field(..., description="Value in standardized unit")
    normalized_unit: str = Field(..., description="Standardized unit (e.g., umol/L, g/L, mmol/L)")
    unit_conversion_factor: float = Field(1.0, description="Logged conversion factor (normalized = raw * factor)")
    mapping_confidence: float = Field(1.0, description="Graph mapping confidence score")
    mapped: bool = Field(True, description="True if mapped to Kuzu graph LabTest node")


class Assessment(BaseModel):
    """Output of Stage D range assessment."""
    normalized_lab_value: NormalizedLabValue
    classification: str = Field(..., description="normal | low | high | critical_low | critical_high | uninterpretable")
    reference_range_used: str = Field(..., description="Normal range bounds string used for classification")
    critical_range_used: Optional[str] = Field(None, description="Critical range bounds string if applicable")
    provenance_row: str = Field(..., description="Provenance string detailing dataset/range row used")
    is_critical: bool = Field(False, description="True if critical_low or critical_high")


class Explanation(BaseModel):
    """Output of Stage E explanation generation with provenance."""
    assessment: Assessment
    what_it_is: str = Field(..., description="Definition of what the test measures")
    what_it_means: str = Field(..., description="Interpretation of user's value against reference range")
    possible_causes: List[str] = Field(default_factory=list, description="Graph-derived associated conditions")
    provenance: List[str] = Field(default_factory=list, description="Strict provenance (graph edges + range rows)")
    disclaimer: str = Field(
        "This is information, not medical advice — consult your physician.",
        description="Mandatory medical disclaimer",
    )


class ReportResult(BaseModel):
    """Final output of ReportInterpretationService."""
    user_id: str
    parsed_summary: str
    lab_values: List[LabValue]
    assessments: List[Assessment]
    explanations: List[Explanation]
    critical_flag: bool = Field(False, description="True if any value in report is critical")
    escalation_text: Optional[str] = Field(None, description="Prominent escalation warning if critical_flag is true")
    private_store_path: str
    provenance: List[str]
    disclaimer: str = "This is information, not medical advice — consult your physician."
    processing_latency_ms: float = 0.0
