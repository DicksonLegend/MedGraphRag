"""
HTML parser — BeautifulSoup with lxml engine
Memory-safe: caps body text for large files.
"""

from pathlib import Path
from bs4 import BeautifulSoup

from config import MAX_TEXT_BODY_CHARS


def parse_html(filepath: Path) -> dict:
    """Parse an HTML file using BeautifulSoup. Memory-safe."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            html = f.read()

        soup = BeautifulSoup(html, "lxml")

        # Extract title
        title = None
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        # Extract and clean body
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        body = soup.get_text(separator="\n", strip=True)

        # Extract tables
        tables = []
        for table in soup.find_all("table"):
            rows = []
            headers = []
            for tr in table.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if not headers:
                    if tr.find_all("th"):
                        headers = cells
                        continue
                if cells:
                    rows.append(cells)
            if headers or rows:
                tables.append({"headers": headers, "rows": rows})

        warnings = []
        if len(body) > MAX_TEXT_BODY_CHARS:
            body = body[:MAX_TEXT_BODY_CHARS]
            warnings.append(f"Body truncated: {len(html)} bytes → {MAX_TEXT_BODY_CHARS} chars stored")

        return {
            "text_body": body,
            "text_title": title,
            "text_abstract": None,
            "page_count": None,
            "structured_data": tables,
            "figures": [],
            "metadata": {"extraction_tool": "BeautifulSoup+lxml", "ocr_used": False},
            "source_metadata": {},
            "extraction_warnings": warnings,
        }
    except Exception as e:
        return {
            "text_body": None,
            "text_title": None,
            "text_abstract": None,
            "page_count": None,
            "structured_data": [],
            "figures": [],
            "metadata": {"extraction_tool": "BeautifulSoup+lxml", "ocr_used": False},
            "source_metadata": {},
            "extraction_warnings": [f"HTML parse error: {e}"],
        }
