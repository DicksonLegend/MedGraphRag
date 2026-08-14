"""
Generate Step 13 Evaluation Test Fixtures:
  - T1a_cmp_report.csv: Baseline CMP report (2026-05-10) with Creatinine 1.1 mg/dL, HbA1c 6.9%, Potassium 4.2 mmol/L.
  - T1b_cmp_report.csv: Followup CMP report (2026-08-12) with Creatinine 1.9 mg/dL, HbA1c 7.8%, Potassium 4.3 mmol/L.
  - T2_diabetes_report.csv: Diabetes report (2026-08-12) with HbA1c 8.2%, Fasting Glucose 180.0 mg/dL, Potassium 4.5 mmol/L (missing Creatinine & Urine Albumin).
"""

import os
from pathlib import Path
import pandas as pd

FIXTURES_DIR = Path("/home/dicksone/Documents/MedGraphRag/evaluations/fixtures")
os.makedirs(FIXTURES_DIR, exist_ok=True)


def generate_t1a_csv():
    """T1a: Baseline CMP report."""
    csv_path = FIXTURES_DIR / "T1a_cmp_report.csv"
    data = {
        "Test Name": ["Creatinine", "Hemoglobin A1c", "Potassium", "Sodium", "Glucose"],
        "Result": ["1.1", "6.9", "4.2", "140.0", "110.0"],
        "Unit": ["mg/dL", "%", "mmol/L", "mmol/L", "mg/dL"],
        "Reference Range": ["0.6 - 1.2", "4.0 - 5.6", "3.5 - 5.1", "135 - 145", "70 - 100"],
    }
    df = pd.DataFrame(data)
    # Header comment with report date
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("# CENTRAL MEDICAL CLINIC — COMPREHENSIVE METABOLIC PANEL\n")
        f.write("# Patient: Alex Mercer | Date: 2026-05-10\n")
        df.to_csv(f, index=False)
    print(f"Generated {csv_path}")


def generate_t1b_csv():
    """T1b: Followup CMP report 3 months later."""
    csv_path = FIXTURES_DIR / "T1b_cmp_report.csv"
    data = {
        "Test Name": ["Creatinine", "Hemoglobin A1c", "Potassium", "Sodium", "Glucose"],
        "Result": ["1.9", "7.8", "4.3", "139.0", "145.0"],
        "Unit": ["mg/dL", "%", "mmol/L", "mmol/L", "mg/dL"],
        "Reference Range": ["0.6 - 1.2", "4.0 - 5.6", "3.5 - 5.1", "135 - 145", "70 - 100"],
    }
    df = pd.DataFrame(data)
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("# CENTRAL MEDICAL CLINIC — COMPREHENSIVE METABOLIC PANEL\n")
        f.write("# Patient: Alex Mercer | Date: 2026-08-12\n")
        df.to_csv(f, index=False)
    print(f"Generated {csv_path}")


def generate_t2_csv():
    """T2: Diabetes report with HbA1c 8.2% but missing renal monitoring (Creatinine / Urine Albumin)."""
    csv_path = FIXTURES_DIR / "T2_diabetes_report.csv"
    data = {
        "Test Name": ["Hemoglobin A1c", "Fasting Glucose", "Potassium", "Sodium"],
        "Result": ["8.2", "180.0", "4.5", "141.0"],
        "Unit": ["%", "mg/dL", "mmol/L", "mmol/L"],
        "Reference Range": ["4.0 - 5.6", "70 - 100", "3.5 - 5.1", "135 - 145"],
    }
    df = pd.DataFrame(data)
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("# METROPOLITAN DIABETES CARE CENTER\n")
        f.write("# Patient: Jordan Lee | Date: 2026-08-12\n")
        df.to_csv(f, index=False)
    print(f"Generated {csv_path}")


if __name__ == "__main__":
    generate_t1a_csv()
    generate_t1b_csv()
    generate_t2_csv()
