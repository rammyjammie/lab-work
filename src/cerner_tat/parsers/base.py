"""Shared parsing logic used by both the HTML and PDF parsers.

The strategy is format-agnostic: every report is reduced to a list of *tables*,
where a table is a list of rows and a row is a list of cell strings. From there
we:

  1. find the header row (the row that matches the most known column aliases),
  2. map canonical fields -> column indexes,
  3. turn each following row into a TestRecord.

This keeps the HTML and PDF parsers tiny — they only have to produce raw tables.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Optional, Sequence

import pandas as pd

from ..config import (
    TAT_FIELDS,
    TIME_FIELDS,
    Config,
    normalize_header,
)
from ..models import TestRecord

Table = List[List[str]]


# ---------------------------------------------------------------------------
# Value parsing
# ---------------------------------------------------------------------------

def parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    """Best-effort parse of a timestamp cell. Returns None if unparseable/empty."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "n/a", "na", "-", "--"}:
        return None
    # pandas handles a wide range of formats offline; coerce failures to NaT.
    ts = pd.to_datetime(text, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.to_pydatetime()


_DUR_HMS = re.compile(r"^\s*(\d+):(\d{2})(?::(\d{2}))?\s*$")
_DUR_TOKENS = re.compile(
    r"(?:(\d+)\s*d)?\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*(?:(\d+)\s*s)?",
    re.IGNORECASE,
)
_PANDAS_DELTA = re.compile(
    r"^\s*(?:(\d+)\s*days?,?\s*)?(\d+):(\d{2}):(\d{2})", re.IGNORECASE
)


def parse_duration_minutes(value: Optional[str]) -> Optional[float]:
    """Parse a TAT cell into minutes.

    Accepts:
      * plain numbers  -> minutes ("83", "83.5")
      * "H:MM" / "HH:MM:SS"
      * pandas timedelta text "1 days 02:03:00"
      * token strings "1d 2h 3m", "2h 30m", "45m"
    Returns None if it can't be parsed.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "n/a", "na", "-", "--"}:
        return None

    # plain number -> minutes
    try:
        return float(text)
    except ValueError:
        pass

    # pandas-style "1 days 02:03:00"
    m = _PANDAS_DELTA.match(text)
    if m:
        days = int(m.group(1) or 0)
        h, mi, s = int(m.group(2)), int(m.group(3)), int(m.group(4))
        return days * 24 * 60 + h * 60 + mi + s / 60.0

    # "H:MM" or "HH:MM:SS"
    m = _DUR_HMS.match(text)
    if m:
        h = int(m.group(1))
        mi = int(m.group(2))
        s = int(m.group(3) or 0)
        return h * 60 + mi + s / 60.0

    # token form "1d 2h 3m 4s" (only if it actually contains a unit letter)
    if re.search(r"[dhms]", text, re.IGNORECASE):
        m = _DUR_TOKENS.match(text)
        if m and any(m.groups()):
            d, h, mi, s = (int(g) if g else 0 for g in m.groups())
            return d * 24 * 60 + h * 60 + mi + s / 60.0

    return None


# ---------------------------------------------------------------------------
# Table -> records
# ---------------------------------------------------------------------------

def _row_match_score(row: Sequence[str], config: Config) -> int:
    """How many canonical fields this row's cells match as headers."""
    normalized_cells = [normalize_header(c) for c in row]
    score = 0
    for aliases in config.column_aliases.values():
        if any(cell in aliases for cell in normalized_cells):
            score += 1
    return score


def _find_header_row(table: Table, config: Config) -> Optional[int]:
    """Index of the row that best looks like a header, or None if nothing matches."""
    best_idx, best_score = None, 0
    for idx, row in enumerate(table):
        score = _row_match_score(row, config)
        if score > best_score:
            best_idx, best_score = idx, score
    return best_idx if best_score >= 2 else None


def _map_columns(header: Sequence[str], config: Config) -> Dict[str, int]:
    """canonical field -> column index, using the configured aliases."""
    normalized = [normalize_header(c) for c in header]
    mapping: Dict[str, int] = {}
    for field_name, aliases in config.column_aliases.items():
        for col_idx, cell in enumerate(normalized):
            if cell and cell in aliases and field_name not in mapping:
                mapping[field_name] = col_idx
                break
    return mapping


def _cell(row: Sequence[str], idx: Optional[int]) -> Optional[str]:
    if idx is None or idx >= len(row):
        return None
    value = row[idx]
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def records_from_table(table: Table, config: Config) -> List[TestRecord]:
    """Extract TestRecords from one raw table, or [] if it isn't a data table."""
    if not table:
        return []
    header_idx = _find_header_row(table, config)
    if header_idx is None:
        return []
    mapping = _map_columns(table[header_idx], config)
    if "test_name" not in mapping:
        # Without a test name we can't classify; skip this table.
        return []

    records: List[TestRecord] = []
    for row in table[header_idx + 1:]:
        if not any(str(c).strip() for c in row):
            continue  # blank row
        test_name = _cell(row, mapping.get("test_name"))
        if not test_name:
            continue  # rows without a test (subtotals, footers) are ignored

        rec = TestRecord(test_name=test_name)
        rec.patient_name = _cell(row, mapping.get("patient_name"))
        rec.mrn = _cell(row, mapping.get("mrn"))
        rec.accession = _cell(row, mapping.get("accession"))

        for tf in TIME_FIELDS:
            raw = _cell(row, mapping.get(tf))
            if raw is not None:
                rec.raw[tf] = raw
                setattr(rec, tf, parse_timestamp(raw))

        for tat in TAT_FIELDS:
            raw = _cell(row, mapping.get(tat))
            if raw is not None:
                rec.raw[tat] = raw
                setattr(rec, tat, parse_duration_minutes(raw))

        records.append(rec)

    return records


def records_from_tables(tables: List[Table], config: Config) -> List[TestRecord]:
    """Run records_from_table across every table and concatenate the results."""
    all_records: List[TestRecord] = []
    for table in tables:
        all_records.extend(records_from_table(table, config))
    return all_records
