"""
Unit Tests for Cross-Modal Discrepancy Guardrail (F1)
=====================================================
DO NOT RUN (Static compile verification only per R1).
Tests pure rule-based logic in app.core.guardrail.discrepancy.
"""

import pytest
from app.core.guardrail.discrepancy import detect_discrepancies
from app.core.guardrail.schemas import DiscrepancyAlert


def test_visual_positive_vs_text_negation_pneumothorax():
    """Rule A: Visual positive (0.88) vs. text negation -> HIGH severity alert."""
    visual_findings = [
        {"label": "pneumothorax", "score": 0.88, "negated": False, "neg_score": 0.12}
    ]
    text_evidence = [
        {
            "snippet": "Chest radiograph demonstrates clear lungs with no pneumothorax or effusion.",
            "source_id": "doc_rad_001",
            "category": "radiology",
        }
    ]

    alerts = detect_discrepancies(visual_findings, text_evidence)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.finding == "pneumothorax"
    assert alert.severity == "HIGH"
    assert alert.visual_evidence.score == 0.88
    assert alert.visual_evidence.negated is False
    assert "manual radiologist review" in alert.recommendation.lower()


def test_visual_negated_vs_text_positive_effusion():
    """Rule B: Visual negated (0.85) vs. text positive assertion -> HIGH severity alert."""
    visual_findings = [
        {"label": "pleural_effusion", "score": 0.15, "negated": True, "neg_score": 0.85}
    ]
    text_evidence = [
        {
            "snippet": "There is moderate bilateral pleural effusion with blunting of the costophrenic angles.",
            "source_id": "doc_rad_002",
            "category": "radiology",
        }
    ]

    alerts = detect_discrepancies(visual_findings, text_evidence)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.finding == "pleural_effusion"
    assert alert.severity == "HIGH"
    assert alert.visual_evidence.negated is True


def test_matching_concordant_findings_no_alert():
    """Concordant visual and textual evidence produces 0 alerts."""
    visual_findings = [
        {"label": "cardiomegaly", "score": 0.85, "negated": False, "neg_score": 0.15}
    ]
    text_evidence = [
        {
            "snippet": "Enlarged cardiac silhouette consistent with cardiomegaly.",
            "source_id": "doc_rad_003",
            "category": "radiology",
        }
    ]

    alerts = detect_discrepancies(visual_findings, text_evidence)
    assert len(alerts) == 0


def test_subthreshold_visual_finding_no_alert():
    """Sub-threshold visual confidence (< 0.60) does not trigger discrepancy alert."""
    visual_findings = [
        {"label": "pneumothorax", "score": 0.42, "negated": False, "neg_score": 0.58}
    ]
    text_evidence = [
        {
            "snippet": "No pneumothorax is identified on the current view.",
            "source_id": "doc_rad_004",
            "category": "radiology",
        }
    ]

    alerts = detect_discrepancies(visual_findings, text_evidence)
    assert len(alerts) == 0


def test_fail_open_on_empty_or_invalid():
    """Fail-open behavior produces empty list without raising exceptions."""
    assert detect_discrepancies([], []) == []
    assert detect_discrepancies(None, None) == []
    assert detect_discrepancies([{"invalid": True}], [{"invalid": True}]) == []
