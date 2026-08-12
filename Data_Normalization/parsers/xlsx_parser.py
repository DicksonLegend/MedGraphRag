"""
XLSX/XLS parser — Pandas (openpyxl engine)
"""

from pathlib import Path
import pandas as pd


def parse_xlsx(filepath: Path) -> dict:
    """Parse an Excel file — each sheet becomes a structured_data entry."""
    try:
        excel_file = pd.ExcelFile(filepath, engine="openpyxl")
        sheet_names = excel_file.sheet_names

        all_data = []
        body_parts = []
        for sheet_name in sheet_names:
            df = pd.read_excel(filepath, sheet_name=sheet_name, engine="openpyxl")
            data = {
                "sheet": sheet_name,
                "headers": df.columns.tolist(),
                "rows": df.values.tolist(),
            }
            all_data.append(data)

            # Build a text representation
            body_parts.append(f"[Sheet: {sheet_name}]")
            body_parts.append(df.to_string(max_rows=200))
            body_parts.append("")

        body = "\n".join(body_parts)

        return {
            "text_body": body,
            "text_title": None,
            "text_abstract": None,
            "page_count": None,
            "structured_data": all_data,
            "figures": [],
            "metadata": {"extraction_tool": "pandas+openpyxl", "ocr_used": False},
            "source_metadata": {},
            "extraction_warnings": [],
        }
    except Exception as e:
        return {
            "text_body": None,
            "text_title": None,
            "text_abstract": None,
            "page_count": None,
            "structured_data": [],
            "figures": [],
            "metadata": {"extraction_tool": "pandas+openpyxl", "ocr_used": False},
            "source_metadata": {},
            "extraction_warnings": [f"XLSX parse error: {e}"],
        }
