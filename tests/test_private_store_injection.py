"""
Regression & Security Tests: Private Store Cypher Injection Prevention (F-01)
=============================================================================
Asserts that malicious, attacker-crafted lab values, test names, and units
(containing single quotes, double quotes, Cypher delimiters '});', UNWIND,
DROP TABLE, and multi-byte Unicode) are stored verbatim via parameterized
Cypher queries without syntax errors or injection escapes.
"""

import os
import shutil
import tempfile
from pathlib import Path

from app.core.report.schemas import (
    Assessment,
    LabValue,
    NormalizedLabValue,
)
from app.core.report.store import store_private_report


def test_private_store_cypher_injection_roundtrip():
    temp_dir = tempfile.mkdtemp()
    user_id = "test_injection_user"
    
    try:
        # Override private store directory to isolated temp path
        from app.config import settings
        orig_private_dir = settings.private_store_dir
        settings.private_store_dir = Path(temp_dir)

        malicious_payloads = [
            ("Potassium'); DROP TABLE LabValue; --", "5.8' OR '1'='1", "mEq/L'; MATCH (n) DETACH DELETE n; --"),
            ("HbA1c \"}; UNWIND range(1, 1000) AS x CREATE (:Injected {val: x})", "7.4% \"); //", "% \" OR 1=1"),
            ("Glucose -- single ' quote and double \" quote", "140.0'; RETURN 1; //", "mg/dL'; --"),
            ("🔬 Blood Urea Nitrogen (BUN) \u2265 20 mg/dL \u2014 \u00e9l\u00e9vation", "25.5 \U0001F9EA", "mg/dL \u00B5L"),
        ]

        assessments = []
        for idx, (t_name, val_raw, unit_raw) in enumerate(malicious_payloads):
            lv = LabValue(
                raw_text=f"{t_name} {val_raw} {unit_raw}",
                test_name_raw=t_name,
                value_raw=5.8 if idx == 0 else 100.0,
                value_raw_str=val_raw,
                unit_raw=unit_raw,
                reference_range_raw="3.5 - 5.0",
            )
            nlv = NormalizedLabValue(
                lab_value=lv,
                canonical_test_name=t_name,
                normalized_value=5.8 if idx == 0 else 100.0,
                normalized_unit=unit_raw,
                unit_conversion_factor=1.0,
                mapping_confidence=1.0,
                mapped=True,
            )
            asm = Assessment(
                normalized_lab_value=nlv,
                classification="abnormal",
                reference_range_used="3.5 - 5.0",
                provenance_row="test_provenance",
                is_critical=(idx == 0),
            )
            assessments.append(asm)

        # Store report
        raw_text = "Date: 2026-08-26\nDiagnostic Report with injection payloads"
        store_path = store_private_report(
            user_id=user_id,
            raw_text=raw_text,
            lab_values=[a.normalized_lab_value.lab_value for a in assessments],
            assessments=assessments,
            explanations=[],
        )

        assert Path(store_path).exists()

        # Connect to the private Kùzu DB and verify all nodes exist with exact verbatim text
        import kuzu
        db_path = Path(store_path) / "kuzu" / "private_kuzu_db"
        assert db_path.exists()

        db = kuzu.Database(str(db_path), read_only=True)
        conn = kuzu.Connection(db)
        
        # Verify Report table
        df_rep = conn.execute("MATCH (r:Report) RETURN r.id, r.report_date, r.filename").get_as_df()
        assert not df_rep.empty
        assert len(df_rep) == 1

        # Verify LabValue table contains exact malicious strings without modification
        df_lv = conn.execute("MATCH (lv:LabValue) RETURN lv.id, lv.test_name, lv.value, lv.unit").get_as_df()
        assert len(df_lv) == len(malicious_payloads)
        
        retrieved_test_names = set(df_lv["lv.test_name"].tolist())
        for t_name, _, _ in malicious_payloads:
            assert t_name in retrieved_test_names

        # Verify PrivateLabValue legacy table
        df_priv = conn.execute("MATCH (p:PrivateLabValue) RETURN p.id, p.test_name, p.val_str").get_as_df()
        assert len(df_priv) == len(malicious_payloads)
        
        retrieved_val_strs = set(df_priv["p.val_str"].tolist())
        for _, val_raw, _ in malicious_payloads:
            assert val_raw in retrieved_val_strs

        print("F-01 Cypher injection prevention test passed successfully!")

    finally:
        settings.private_store_dir = orig_private_dir
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    test_private_store_cypher_injection_roundtrip()
