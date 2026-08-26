"""
MedGraphRAG Backend — Cross-Modal Discrepancy Guardrail (F1)
============================================================
Pure, rule-based deterministic guardrail that compares visual findings from
radiology imaging (BiomedCLIP/VLM) against textual evidence (reports, retrieved
clinical snippets, or EHR notes).

Core Principles:
  1. ESCALATE, NEVER AUTO-RESOLVE: The AI flags contradictions for human clinician review.
  2. DETERMINISTIC & ZERO-LLM: Fast, rule-based matching with zero VRAM/LLM latency.
  3. READ-ONLY GRAPH PROVENANCE: Read-only check against report_graph/kuzu.db when study/image ID is known.
  4. FAIL-OPEN: Returns empty list on any runtime error.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from app.config import PROJECT_ROOT, settings
from app.core.guardrail.schemas import (
    DiscrepancyAlert,
    DiscrepancyTextEvidence,
    DiscrepancyVisualEvidence,
)

logger = logging.getLogger(__name__)

# ── Life-Critical Findings (Trigger HIGH Severity) ───────────────────────────
CRITICAL_FINDINGS: Set[str] = {
    "pneumothorax",
    "pleural_effusion",
    "pleural effusion",
    "edema",
    "pulmonary edema",
    "consolidation",
    "cardiomegaly",
    "fracture",
    "rib fracture",
}

# ── Finding Synonyms & Keywords ──────────────────────────────────────────────
FINDING_SYNONYMS: Dict[str, List[str]] = {
    "pneumothorax": ["pneumothorax", "pneumothoraces", "ptx", "air in the pleural space", "apical pneumothorax"],
    "pleural_effusion": ["pleural effusion", "pleural effusions", "effusion", "fluid in pleural space", "pleural fluid", "costophrenic blunting"],
    "edema": ["pulmonary edema", "edema", "pulmonary congestion", "alveolar edema", "interstitial edema", "fluid overload", "vascular congestion"],
    "consolidation": ["consolidation", "consolidations", "airspace opacity", "airspace opacities", "infiltrate", "infiltrates", "pulmonary infiltrate", "pneumonia"],
    "cardiomegaly": ["cardiomegaly", "enlarged heart", "cardiac enlargement", "enlarged cardiac silhouette", "prominent cardiopericardial silhouette"],
    "fracture": ["fracture", "fractures", "broken bone", "cortical break", "cortical disruption", "rib fracture", "clavicle fracture"],
    "atelectasis": ["atelectasis", "lung collapse", "linear atelectasis", "bibasilar atelectasis", "subsegmental atelectasis", "plate-like atelectasis"],
    "nodule": ["nodule", "nodules", "pulmonary nodule", "mass", "pulmonary mass", "granuloma", "lung lesion", "coin lesion"],
    "opacity": ["opacity", "opacities", "density", "densities", "hazy density", "ground glass"],
}

# ── Clinical Negation Cues (Ordered by length for greedy match) ──────────────
NEGATION_CUES: List[str] = [
    "no evidence of",
    "no sign of",
    "no signs of",
    "no definite",
    "without evidence of",
    "without sign of",
    "free of",
    "ruled out",
    "rules out",
    "negative for",
    "clear of",
    "clear lungs",
    "lungs are clear",
    "no acute",
    "not seen",
    "unremarkable",
    "unlikely",
    "absent",
    "denies",
    "without",
    "no",
    "not",
    "neither",
]


def _normalize_finding_name(label: str) -> str:
    """Normalize finding label to lower snake_case/cleaned string."""
    cleaned = label.strip().lower().replace("-", "_").replace(" ", "_")
    return cleaned


def _get_synonyms_for_finding(label: str) -> List[str]:
    """Retrieve synonym search patterns for a finding."""
    norm = _normalize_finding_name(label)
    for key, syns in FINDING_SYNONYMS.items():
        if norm == key or norm in [s.replace(" ", "_") for s in syns] or key in norm:
            return syns
    # Fallback to the raw label and space/underscore variations
    raw = label.strip().lower()
    return [raw, raw.replace("_", " "), raw.replace(" ", "_")]


def _check_text_negation(snippet: str, finding_kw: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a text snippet mentions finding_kw with an associated clinical negation cue.
    Returns (is_negated, matched_cue).
    """
    snippet_lower = snippet.lower()
    kw_pos = snippet_lower.find(finding_kw.lower())
    if kw_pos == -1:
        return False, None

    # Analyze preceding window of up to 60 characters and current sentence
    start_win = max(0, kw_pos - 60)
    preceding_text = snippet_lower[start_win:kw_pos]

    # Stop at previous sentence boundary if present
    for delim in [". ", "; ", "\n"]:
        if delim in preceding_text:
            preceding_text = preceding_text.split(delim)[-1]

    # Check for preceding negation cue
    for cue in NEGATION_CUES:
        cue_pattern = rf"\b{re.escape(cue)}\b"
        if re.search(cue_pattern, preceding_text):
            return True, cue

    # Check for following negation cue (e.g., "pneumothorax is absent / ruled out / not seen")
    end_win = min(len(snippet_lower), kw_pos + len(finding_kw) + 40)
    following_text = snippet_lower[kw_pos + len(finding_kw):end_win]
    for delim in [". ", "; ", "\n"]:
        if delim in following_text:
            following_text = following_text.split(delim)[0]

    for cue in ["is absent", "are absent", "is ruled out", "is not seen", "was not identified", "is unremarkable"]:
        if cue in following_text:
            return True, cue

    return False, None


def _query_report_graph_provenance(graph_ctx: str, finding_name: str) -> Optional[str]:
    """
    Read-only check against report_graph/kuzu.db if graph_ctx (e.g. OpenI image/study ID) is provided.
    Never alters or writes to the database.
    """
    if not graph_ctx:
        return None

    graph_db_path = PROJECT_ROOT / "data" / "multimodal" / "report_graph" / "kuzu.db"
    if not graph_db_path.exists():
        return None

    try:
        import kuzu
        db = kuzu.Database(str(graph_db_path), read_only=True)
        conn = kuzu.Connection(db)

        # Check if study/image node links to this finding
        norm_finding = finding_name.lower().replace("_", " ")
        q = """
        MATCH (img:Image)-[:IMAGE_SHOWS]->(vf:VisualFinding)
        WHERE (img.id = $ctx OR img.study_id = $ctx)
          AND (to_lower(vf.label) CONTAINS $f_name)
        RETURN img.id AS image_id, vf.label AS label, vf.negated AS negated
        LIMIT 1
        """
        res = conn.execute(q, {"ctx": str(graph_ctx), "f_name": norm_finding})
        if res.has_next():
            row = res.get_next()
            img_id, lbl, neg = row[0], row[1], row[2]
            neg_str = "NEGATED" if neg else "POSITIVE"
            return f"(Image:{img_id}) -[:IMAGE_SHOWS]-> (VisualFinding:{lbl} [{neg_str}]) in report_graph"
    except Exception as e:
        logger.debug("Read-only report_graph provenance check skipped: %s", e)

    return None


def detect_discrepancies(
    visual_findings: List[Any],
    text_evidence: List[Any],
    graph_ctx: Optional[str] = None,
) -> List[DiscrepancyAlert]:
    """
    Detect cross-modal contradictions between visual findings and clinical text.

    Parameters
    ----------
    visual_findings : list
        List of visual finding dicts or VisualFinding objects:
        [{label, score, negated, neg_score}, ...]
    text_evidence : list
        List of text evidence dicts or EvidenceItem objects:
        [{snippet, source_id, category}, ...]
    graph_ctx : str, optional
        Optional image_id or study_id for read-only report_graph corroboration.

    Returns
    -------
    List[DiscrepancyAlert]
        List of escalated discrepancy alerts (empty if no conflicts).
    """
    if not settings.enable_discrepancy_guardrail:
        return []

    if not visual_findings or not text_evidence:
        return []

    alerts: List[DiscrepancyAlert] = []
    seen_alerts: Set[str] = set()

    try:
        # Normalize visual findings
        normalized_vf: List[Dict[str, Any]] = []
        for vf in visual_findings:
            if hasattr(vf, "model_dump"):
                d = vf.model_dump()
            elif isinstance(vf, dict):
                d = dict(vf)
            else:
                continue

            lbl = d.get("label") or d.get("finding") or ""
            if not lbl:
                continue

            score = float(d.get("score", d.get("confidence", 0.0)))
            neg = bool(d.get("negated", False))
            neg_score = float(d.get("neg_score", score if neg else (1.0 - score)))

            normalized_vf.append({
                "label": lbl,
                "score": score,
                "negated": neg,
                "neg_score": neg_score,
            })

        # Normalize text evidence
        normalized_txt: List[Dict[str, Any]] = []
        for te in text_evidence:
            if hasattr(te, "model_dump"):
                d = te.model_dump()
            elif isinstance(te, dict):
                d = dict(te)
            else:
                continue

            snip = d.get("snippet") or d.get("text") or ""
            src = d.get("source_id") or d.get("chunk_id") or d.get("document_id") or "clinical_text"
            cat = d.get("category") or "radiology"
            if snip:
                normalized_txt.append({
                    "snippet": snip,
                    "source_id": src,
                    "category": cat,
                })

        # Compare each visual finding against text evidence
        for vf in normalized_vf:
            v_label = vf["label"]
            v_score = vf["score"]
            v_neg = vf["negated"]
            v_neg_score = vf["neg_score"]
            synonyms = _get_synonyms_for_finding(v_label)

            v_is_positive = (v_score >= 0.60 and not v_neg)
            v_is_negated = (v_neg_score >= 0.60 or (v_neg and v_score >= 0.60))

            if not v_is_positive and not v_is_negated:
                continue  # Finding is equivocal / below detection threshold

            for te in normalized_txt:
                snippet = te["snippet"]
                snippet_lower = snippet.lower()

                # Check if any synonym matches this snippet
                matched_syn = None
                for syn in synonyms:
                    if re.search(rf"\b{re.escape(syn.lower())}\b", snippet_lower):
                        matched_syn = syn
                        break

                if not matched_syn:
                    continue

                text_is_negated, matched_cue = _check_text_negation(snippet, matched_syn)

                # Rule A: Visual positive (>=0.6) + Text asserts negation -> DISCREPANCY
                rule_a = (v_is_positive and text_is_negated)

                # Rule B: Visual negated (>=0.6) + Text asserts finding positively -> DISCREPANCY
                rule_b = (v_is_negated and not text_is_negated)

                if rule_a or rule_b:
                    alert_key = f"{_normalize_finding_name(v_label)}_{te['source_id']}"
                    if alert_key in seen_alerts:
                        continue
                    seen_alerts.add(alert_key)

                    # Determine severity
                    norm_name = _normalize_finding_name(v_label)
                    is_critical = any(
                        cf == norm_name or cf in norm_name or norm_name in cf
                        for cf in CRITICAL_FINDINGS
                    )
                    severity = "HIGH" if is_critical else "MEDIUM"

                    # Check graph provenance if available (read-only)
                    graph_prov = _query_report_graph_provenance(graph_ctx, v_label) if graph_ctx else None

                    alert = DiscrepancyAlert(
                        finding=v_label,
                        visual_evidence=DiscrepancyVisualEvidence(
                            label=v_label,
                            score=v_score,
                            negated=v_neg,
                            neg_score=v_neg_score,
                        ),
                        text_evidence=DiscrepancyTextEvidence(
                            snippet=snippet.strip(),
                            source_id=te["source_id"],
                            cue=matched_cue if matched_cue else ("asserted_present" if not text_is_negated else "negated"),
                            category=te.get("category"),
                        ),
                        graph_provenance=graph_prov,
                        severity=severity,
                        recommendation="AI does not resolve this conflict — recommend manual radiologist review.",
                    )
                    alerts.append(alert)
                    logger.warning(
                        "🚨 Cross-Modal Discrepancy Alert: finding=%s, severity=%s, visual(score=%.2f, neg=%s) vs text(src=%s, cue=%s)",
                        v_label, severity, v_score, v_neg, te["source_id"], matched_cue
                    )

    except Exception as exc:
        logger.warning("Discrepancy guardrail fail-open: caught unexpected exception: %s", exc)
        return []

    return alerts
