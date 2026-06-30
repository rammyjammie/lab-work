"""Parser for *pasted* / plain-text Cerner TAT reports.

Cerner's TAT report, when copied out of the viewer (or exported as a text-based
PDF), comes through as a flat sequence of lines — one field per line — with each
test laid out as a fixed block:

    <test name>
    <priority code>        (e.g. ST = Stat; optional)
    <order date/time>
    <collected date/time>
    <received date/time>
    <complete date/time>
    <order to collected>    \
    <collected to lab>       |
    <collected to complete>  > the five TAT values, in minutes
    <lab to complete>        |
    <order to complete>     /

There are no column headers in the pasted text, so the fields are read
*positionally*. The order of the timestamp and TAT lines is configurable via the
`text_layout` section of config.yaml, so it can be matched to your report if it
differs.

This parser is datetime-anchored and resynchronizing: it locates each record by
its run of timestamp lines, which makes it tolerant of stray title/header lines
in a paste.
"""

from __future__ import annotations

import re
from typing import List, Optional

from ..config import Config
from ..models import TestRecord
from .base import parse_duration_minutes, parse_timestamp

# A timestamp line like "06/17/2026 07:54" (seconds and AM/PM optional).
_DATETIME_RE = re.compile(
    r"^\d{1,2}/\d{1,2}/\d{2,4}\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?$"
)
# A numeric TAT line: integer or decimal, optionally negative (iSTAT can be < 0).
_NUMBER_RE = re.compile(r"^-?\d+(?:\.\d+)?$")


def _is_datetime(line: str) -> bool:
    return bool(_DATETIME_RE.match(line))


def _is_number(line: str) -> bool:
    return bool(_NUMBER_RE.match(line))


def _split_head(head: List[str], config: Config) -> tuple[str, Optional[str]]:
    """Split the lines before the timestamps into (test_name, priority).

    Only the last one or two lines are meaningful: the test name, optionally
    preceded... no — followed by a priority code line. Any earlier lines are
    report titles/headers picked up before the record and are discarded.
    """
    last = head[-1].strip()
    norm = last.upper()
    is_priority = norm in config.text_priority_codes or (
        len(last) <= 3 and last.isalpha() and last.isupper()
    )
    if is_priority:
        name = head[-2].strip() if len(head) >= 2 else ""
        return name, last
    return last, None


def parse_text(text: str, config: Config) -> List[TestRecord]:
    """Parse pasted/plain report text into TestRecords."""
    # Tab-separated pastes -> one field per line, so the line logic below works.
    text = text.replace("\t", "\n")
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]

    dt_fields = config.text_datetime_fields
    tat_fields = config.text_tat_fields
    max_dt = len(dt_fields)
    max_tat = len(tat_fields)

    records: List[TestRecord] = []
    i, n = 0, len(lines)

    while i < n:
        start = i

        # 1) header lines: everything that's neither a timestamp nor a number
        head: List[str] = []
        while i < n and not _is_datetime(lines[i]) and not _is_number(lines[i]):
            head.append(lines[i])
            i += 1
            if len(head) > max_dt:  # safety: don't run away on a wall of text
                break

        # 2) the run of timestamps
        times: List[str] = []
        while i < n and _is_datetime(lines[i]) and len(times) < max_dt:
            times.append(lines[i])
            i += 1

        if not head or not times:
            # not a record start; advance one line and resync
            i = start + 1
            continue

        # 3) the trailing TAT numbers
        nums: List[str] = []
        while i < n and _is_number(lines[i]) and len(nums) < max_tat:
            nums.append(lines[i])
            i += 1

        test_name, priority = _split_head(head, config)
        rec = TestRecord(test_name=test_name)
        if priority:
            rec.raw["priority"] = priority

        for field_name, value in zip(dt_fields, times):
            rec.raw[field_name] = value
            setattr(rec, field_name, parse_timestamp(value))

        for field_name, value in zip(tat_fields, nums):
            rec.raw[field_name] = value
            setattr(rec, field_name, parse_duration_minutes(value))

        records.append(rec)

    return records


def parse_text_file(path: str, config: Config) -> List[TestRecord]:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return parse_text(fh.read(), config)
