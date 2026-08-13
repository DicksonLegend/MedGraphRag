"""
Generate synthetic evaluation test fixtures F1 (PDF), F2 (PNG), and F3 (XLSX).
"""

import os
from pathlib import Path
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

FIXTURES_DIR = Path("/home/dicksone/Documents/MedGraphRag/evaluations/fixtures")
os.makedirs(FIXTURES_DIR, exist_ok=True)


def generate_f1_pdf():
    """F1: Synthetic CBC/CMP lab report PDF with seeded critical value Potassium 6.8 mmol/L."""
    pdf_path = FIXTURES_DIR / "F1_sample_cbc_cmp.pdf"
    doc = SimpleDocTemplate(str(pdf_path), pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("<b>CENTRAL MEDICAL LABORATORY REPORT</b>", styles["Heading1"]))
    story.append(Paragraph("Patient: Jane Doe | Age: 45 | Sex: Female | Date: 2026-08-12", styles["Normal"]))
    story.append(Spacer(1, 12))

    data = [
        ["Test Name", "Result", "Units", "Reference Range"],
        ["Potassium", "6.8", "mmol/L", "3.5 - 5.1"],
        ["Hemoglobin", "13.5", "g/dL", "12.0 - 16.0"],
        ["Creatinine (KFT)", "95.0", "µmol/L", "53 - 115"],
        ["Sodium", "140.0", "mmol/L", "135 - 145"],
        ["Glucose", "5.2", "mmol/L", "3.9 - 5.6"],
    ]

    t = Table(data, colWidths=[150, 80, 80, 120])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
    ]))
    story.append(t)
    doc.build(story)
    print(f"Generated {pdf_path}")


def generate_f2_image():
    """F2: Image (PNG) of lab report testing OCR."""
    img_path = FIXTURES_DIR / "F2_sample_lab_image.png"
    img = Image.new("RGB", (600, 300), color=(255, 255, 255))
    d = ImageDraw.Draw(img)

    lines = [
        "METROPOLITAN LAB DIAGNOSTICS",
        "WBC Count: 14.5 10^9/L (4.0-11.0)",
        "Hemoglobin: 8.0 g/dL (12.0-16.0)",
        "Platelet Count: 250 10^9/L (150-450)",
    ]

    y = 30
    for l in lines:
        d.text((40, y), l, fill=(0, 0, 0))
        y += 50

    img.save(img_path)
    print(f"Generated {img_path}")


def generate_f3_xlsx():
    """F3: XLSX spreadsheet with 5 lab rows including mixed units (mg/dL and µmol/L)."""
    xlsx_path = FIXTURES_DIR / "F3_sample_lab_data.xlsx"

    data = {
        "Test Name": ["Creatinine", "Glucose", "Hemoglobin", "Sodium", "Potassium"],
        "Result": ["4.0", "90.0", "13.0", "142.0", "4.2"],
        "Unit": ["mg/dL", "mg/dL", "g/dL", "mmol/L", "mmol/L"],
        "Reference Range": ["0.6 - 1.2", "70 - 100", "12.0 - 16.0", "135 - 145", "3.5 - 5.1"],
    }

    df = pd.DataFrame(data)
    df.to_excel(xlsx_path, index=False, engine="openpyxl")
    print(f"Generated {xlsx_path}")


if __name__ == "__main__":
    generate_f1_pdf()
    generate_f2_image()
    generate_f3_xlsx()
