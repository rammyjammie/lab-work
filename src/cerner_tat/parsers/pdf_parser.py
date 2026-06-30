"""PDF report parser.

Uses pdfplumber (local, offline) to pull tables out of each page. Falls back to
nothing if the PDF has no detectable tables — in that case the report is likely
free-text and the parser would need to be adapted to its specific layout.
"""

from __future__ import annotations

from typing import List

import pdfplumber

from ..config import Config
from ..models import TestRecord
from .base import Table, records_from_tables
from .text_parser import parse_text


def _extract(path: str) -> tuple[List[Table], str]:
    """Return (tables, all_text) from a PDF in one pass."""
    tables: List[Table] = []
    text_parts: List[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for raw in page.extract_tables() or []:
                rows: Table = []
                for row in raw:
                    rows.append([("" if c is None else str(c)).strip() for c in row])
                if rows:
                    tables.append(rows)
            text_parts.append(page.extract_text() or "")
    return tables, "\n".join(text_parts)


def parse_pdf(path: str, config: Config) -> List[TestRecord]:
    tables, text = _extract(path)

    # 1) try real tables (a tabular HTML-style export converted to PDF)
    records = records_from_tables(tables, config)
    if records:
        return records

    # 2) fall back to the positional text parser (text-based but non-tabular PDF)
    records = parse_text(text, config)
    if records:
        return records

    # 3) nothing extractable -> almost certainly an image/scanned PDF
    if not text.strip():
        raise ValueError(
            "No text could be extracted from this PDF — it looks like a scanned "
            "image or screenshot. Copy the report text and use the 'Paste text' "
            "option (or save it as a .txt file) instead."
        )
    raise ValueError(
        "The PDF text was extracted but no test records were recognized. "
        "Check the text_layout / column settings in config.yaml, or paste the "
        "report text to verify the layout."
    )
