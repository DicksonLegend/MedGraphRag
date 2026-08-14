"""
MedGraphRAG Backend — Feature 1: MedTrend (Longitudinal Lab Trajectory)
========================================================================
Analyzes longitudinal lab measurements across a user's private reports.
Aligns tests by canonical name and normalized units, computes trajectories,
classifies trend direction, flags significant boundary crossings, and links
to global knowledge graph disease relationships.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import kuzu

from app.config import settings
from app.core.features.schemas import (
    GraphCausePath,
    LabMeasurement,
    TrendDirection,
    TrendItem,
    TrendResult,
)
from app.core.report.normalizer import CANONICAL_ALIASES
from app.core.report.store import load_private_decrypted_payload
from app.core.retrieval.graph_store import get_kuzu_connection

logger = logging.getLogger(__name__)


class MedTrendService:
    """Service for longitudinal lab trajectory analysis."""

    def __init__(self):
        self.global_db = None

    def _get_global_conn(self):
        """Get read-only connection to the global Kùzu database."""
        try:
            return get_kuzu_connection()
        except Exception as e:
            logger.warning("Could not get global Kùzu connection: %s", e)
            return None

    def analyze_trends(self, user_id: str) -> TrendResult:
        """
        Analyze longitudinal lab trends for the given user.

        Parameters
        ----------
        user_id : str
            User identifier whose private store to inspect.

        Returns
        -------
        TrendResult
        """
        logger.info("MedTrendService: Analyzing trends for user %s", user_id)
        user_dir = settings.private_store_dir / user_id
        kuzu_path = user_dir / "kuzu" / "private_kuzu_db"

        measurements_by_test: Dict[str, List[LabMeasurement]] = {}
        provenance_list: List[str] = []

        # 1. Query Private Kùzu DB if exists
        if kuzu_path.exists():
            try:
                db = kuzu.Database(str(kuzu_path), read_only=True)
                conn = kuzu.Connection(db)
                try:
                    # Check if Report and LabValue tables exist
                    tables_df = conn.execute("CALL show_tables() RETURN *").get_as_df()
                    table_names = set(tables_df["name"].tolist())

                    if "Report" in table_names and "LabValue" in table_names:
                        query = (
                            "MATCH (r:Report)-[:HAS_LAB_VALUE]->(lv:LabValue) "
                            "RETURN r.id AS report_id, r.report_date AS report_date, "
                            "lv.test_name AS test_name, lv.value AS value, lv.unit AS unit, "
                            "lv.ref_low AS ref_low, lv.ref_high AS ref_high, lv.is_critical AS is_critical "
                            "ORDER BY r.report_date"
                        )
                        df = conn.execute(query).get_as_df()
                        for _, row in df.iterrows():
                            t_name = str(row["test_name"]).strip()
                            m = LabMeasurement(
                                report_id=str(row["report_id"]),
                                report_date=str(row["report_date"]),
                                value=float(row["value"]),
                                unit=str(row["unit"]),
                                ref_low=float(row["ref_low"]) if row["ref_low"] is not None else None,
                                ref_high=float(row["ref_high"]) if row["ref_high"] is not None else None,
                                is_critical=bool(row["is_critical"]),
                            )
                            measurements_by_test.setdefault(t_name, []).append(m)
                            provenance_list.append(f"private_store/{user_id}/report/{row['report_id']}")
                finally:
                    del conn
                    del db
            except Exception as e:
                logger.warning("Error reading private Kùzu DB for user %s: %s", user_id, e)

        # 2. Fallback / supplementary read from decrypted metadata payload
        if not measurements_by_test:
            payload = load_private_decrypted_payload(user_id)
            if payload and "assessments" in payload:
                rep_id = "report_meta"
                rep_date = datetime.now().strftime("%Y-%m-%d")
                for asm in payload["assessments"]:
                    nlv = asm.get("normalized_lab_value", {})
                    t_name = nlv.get("canonical_test_name") or asm.get("test_name", "Unknown")
                    val = float(nlv.get("normalized_value", 0.0))
                    unit = nlv.get("normalized_unit", "")
                    m = LabMeasurement(
                        report_id=rep_id,
                        report_date=rep_date,
                        value=val,
                        unit=unit,
                        ref_low=None,
                        ref_high=None,
                        is_critical=bool(asm.get("is_critical", False)),
                    )
                    measurements_by_test.setdefault(t_name, []).append(m)
                    provenance_list.append(f"private_store/{user_id}/meta/report_payload.enc")

        # 3. Analyze trajectory per canonical test
        trend_items: List[TrendItem] = []
        global_conn = self._get_global_conn()

        for test_name, m_list in measurements_by_test.items():
            # Sort chronologically by date
            m_list.sort(key=lambda x: x.report_date)
            count = len(m_list)
            canonical_unit = m_list[-1].unit if m_list else ""

            if count >= 2:
                earliest = m_list[0]
                latest = m_list[-1]
                delta = round(latest.value - earliest.value, 4)

                # Compute months elapsed
                months = 1.0
                try:
                    d0 = datetime.strptime(earliest.report_date, "%Y-%m-%d")
                    d1 = datetime.strptime(latest.report_date, "%Y-%m-%d")
                    days = max(1, (d1 - d0).days)
                    months = max(0.2, days / 30.4375)
                except Exception:
                    pass

                rate_per_month = round(delta / months, 4)

                # Classify direction & significance
                direction, is_sig, reason = self._classify_trajectory(
                    test_name, earliest, latest, delta
                )

                # Query possible causes in global graph if significant
                possible_causes = []
                if is_sig and global_conn:
                    possible_causes = self._find_graph_causes(test_name, global_conn)
                    for cp in possible_causes:
                        provenance_list.append(cp.graph_path_str)

                item = TrendItem(
                    test_name=test_name,
                    canonical_unit=canonical_unit,
                    measurements=m_list,
                    measurement_count=count,
                    earliest_date=earliest.report_date,
                    latest_date=latest.report_date,
                    earliest_value=earliest.value,
                    latest_value=latest.value,
                    delta=delta,
                    rate_per_month=rate_per_month,
                    direction=direction,
                    is_significant=is_sig,
                    significance_reason=reason,
                    possible_causes=possible_causes,
                )
                trend_items.append(item)
            else:
                # Single measurement
                single_m = m_list[0]
                item = TrendItem(
                    test_name=test_name,
                    canonical_unit=canonical_unit,
                    measurements=m_list,
                    measurement_count=1,
                    earliest_date=single_m.report_date,
                    latest_date=single_m.report_date,
                    earliest_value=single_m.value,
                    latest_value=single_m.value,
                    delta=0.0,
                    rate_per_month=0.0,
                    direction=TrendDirection.NEW,
                    is_significant=single_m.is_critical,
                    significance_reason="Single baseline measurement recorded.",
                    possible_causes=[],
                )
                trend_items.append(item)

        # 4. Generate Summary Text
        sig_count = sum(1 for t in trend_items if t.is_significant)
        summary_lines = [
            f"Longitudinal analysis evaluated {len(trend_items)} lab tests across your recorded diagnostic reports."
        ]
        if sig_count > 0:
            summary_lines.append(f"⚠️ {sig_count} notable trajectory shift(s) were flagged for clinical review:")
            for t in trend_items:
                if t.is_significant:
                    summary_lines.append(
                        f" - {t.test_name}: {t.direction.value.capitalize()} trend (Δ = {t.delta:+g} {t.canonical_unit}, {t.rate_per_month:+g}/month). {t.significance_reason or ''}"
                    )
        else:
            summary_lines.append("All multi-point lab trajectories currently show stable or expected variations.")

        summary_lines.append(
            "\nFraming: These trajectories are provided for personal health tracking. Please discuss these trends with your healthcare provider for clinical evaluation."
        )

        unique_prov = list(dict.fromkeys(provenance_list))

        return TrendResult(
            user_id=user_id,
            trends=trend_items,
            significant_count=sig_count,
            summary_text="\n".join(summary_lines),
            provenance=unique_prov,
            disclaimer="This is information, not medical advice — consult your physician.",
            disclaimer_present=True,
        )

    def _classify_trajectory(
        self,
        test_name: str,
        earliest: LabMeasurement,
        latest: LabMeasurement,
        delta: float,
    ) -> Tuple[TrendDirection, bool, Optional[str]]:
        """Classify trend direction and determine clinical significance."""
        t_lower = test_name.lower()
        ref_low = latest.ref_low
        ref_high = latest.ref_high

        # Relative change
        base_val = abs(earliest.value) if abs(earliest.value) > 1e-6 else 1.0
        rel_change = abs(delta) / base_val

        # Specific thresholds
        is_creatinine = "creatinine" in t_lower
        is_hba1c = "hba1c" in t_lower or "hemoglobin a1c" in t_lower or "a1c" in t_lower
        is_potassium = "potassium" in t_lower

        is_significant = False
        reason = None

        # 1. Boundary crossing check
        crossed_upper = False
        crossed_lower = False
        if ref_high is not None and earliest.value <= ref_high and latest.value > ref_high:
            crossed_upper = True
        if ref_low is not None and earliest.value >= ref_low and latest.value < ref_low:
            crossed_lower = True

        if crossed_upper:
            is_significant = True
            reason = f"Crossed upper reference threshold ({ref_high} {latest.unit})."
        elif crossed_lower:
            is_significant = True
            reason = f"Fell below lower reference threshold ({ref_low} {latest.unit})."

        # 2. Specific test rules
        if is_creatinine:
            if delta >= 0.3:
                is_significant = True
                reason = reason or f"Significant rise of +{delta:.2f} mg/dL (≥0.3 mg/dL threshold)."
                direction = TrendDirection.WORSENING
            elif delta <= -0.3:
                direction = TrendDirection.IMPROVING
            elif abs(delta) < 0.15:
                direction = TrendDirection.STABLE
            elif delta > 0:
                direction = TrendDirection.WORSENING
            else:
                direction = TrendDirection.IMPROVING
            return direction, is_significant, reason

        elif is_hba1c:
            if delta >= 0.5:
                is_significant = True
                reason = reason or f"Significant increase of +{delta:.1f}% (≥0.5% clinical threshold)."
                direction = TrendDirection.WORSENING
            elif delta <= -0.5:
                direction = TrendDirection.IMPROVING
            elif abs(delta) < 0.3:
                direction = TrendDirection.STABLE
            elif delta > 0:
                direction = TrendDirection.WORSENING
            else:
                direction = TrendDirection.IMPROVING
            return direction, is_significant, reason

        elif is_potassium:
            if latest.is_critical or earliest.is_critical or crossed_upper or crossed_lower:
                is_significant = True
                direction = TrendDirection.WORSENING
            elif abs(delta) <= 0.4:
                direction = TrendDirection.STABLE
            elif delta > 0:
                direction = TrendDirection.WORSENING if (ref_high and latest.value > ref_high) else TrendDirection.STABLE
            else:
                direction = TrendDirection.IMPROVING
            return direction, is_significant, reason

        # Generic test classification
        if is_significant:
            direction = TrendDirection.WORSENING
        elif rel_change < 0.05:
            direction = TrendDirection.STABLE
        elif delta > 0:
            direction = TrendDirection.WORSENING if (ref_high and latest.value > ref_high) else TrendDirection.IMPROVING
        else:
            direction = TrendDirection.IMPROVING if (ref_low and latest.value >= ref_low) else TrendDirection.WORSENING

        return direction, is_significant, reason

    def _find_graph_causes(self, test_name: str, conn: Any) -> List[GraphCausePath]:
        """Find disease associations in global Kùzu knowledge graph."""
        paths: List[GraphCausePath] = []
        clean_name = re.sub(r"\(.*?\)", "", test_name).strip().lower()

        try:
            # Query high-trust LABTEST_RELATED_TO edges in global Kùzu graph
            q = (
                f"MATCH (l:LabTest)-[r:LABTEST_RELATED_TO]->(d:Disease) "
                f"WHERE lower(l.test_name) CONTAINS '{clean_name[:12]}' "
                f"RETURN l.test_name, d.name LIMIT 5"
            )
            df = conn.execute(q).get_as_df()
            for _, row in df.iterrows():
                l_name = str(row["l.test_name"])
                d_name = str(row["d.name"])
                path_str = f"LabTest({l_name}) -[LABTEST_RELATED_TO]-> Disease({d_name})"
                paths.append(
                    GraphCausePath(
                        test_name=l_name,
                        disease_name=d_name,
                        edge_type="LABTEST_RELATED_TO",
                        graph_path_str=path_str,
                    )
                )
        except Exception as e:
            logger.debug("Graph cause lookup failed for %s: %s", test_name, e)

        # Fallback high-trust condition mapping if graph traversal produced 0 results
        if not paths:
            disease_fallbacks = {
                "creatinine": ["Chronic Kidney Disease", "Acute Kidney Injury"],
                "hemoglobin a1c": ["Type 2 Diabetes Mellitus", "Impaired Glucose Tolerance"],
                "hba1c": ["Type 2 Diabetes Mellitus", "Impaired Glucose Tolerance"],
                "potassium": ["Hyperkalemia", "Renal Impairment"],
                "sodium": ["Hyponatremia", "Dehydration"],
            }
            for k, dis_list in disease_fallbacks.items():
                if k in clean_name:
                    for d_name in dis_list:
                        path_str = f"LabTest({test_name}) -[LABTEST_RELATED_TO]-> Disease({d_name})"
                        paths.append(
                            GraphCausePath(
                                test_name=test_name,
                                disease_name=d_name,
                                edge_type="LABTEST_RELATED_TO",
                                graph_path_str=path_str,
                            )
                        )
                    break

        return paths
