"""HTML report parser.

Reads the file locally (no network), finds every <table>, and reduces each to a
list-of-rows-of-cells that the shared logic in base.py turns into records.
"""

from __future__ import annotations

from typing import List

from bs4 import BeautifulSoup

from ..config import Config
from ..models import TestRecord
from .base import Table, records_from_tables


def _extract_tables(html: str) -> List[Table]:
    soup = BeautifulSoup(html, "lxml")
    tables: List[Table] = []
    for table_el in soup.find_all("table"):
        rows: Table = []
        for tr in table_el.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            if not cells:
                continue
            rows.append([c.get_text(separator=" ", strip=True) for c in cells])
        if rows:
            tables.append(rows)
    return tables


def parse_html(path: str, config: Config) -> List[TestRecord]:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        html = fh.read()
    tables = _extract_tables(html)
    return records_from_tables(tables, config)
