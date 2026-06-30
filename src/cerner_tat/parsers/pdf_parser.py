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


def _extract_tables(path: str) -> List[Table]:
    tables: List[Table] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for raw in page.extract_tables() or []:
                rows: Table = []
                for row in raw:
                    rows.append([("" if c is None else str(c)).strip() for c in row])
                if rows:
                    tables.append(rows)
    return tables


def parse_pdf(path: str, config: Config) -> List[TestRecord]:
    tables = _extract_tables(path)
    return records_from_tables(tables, config)
