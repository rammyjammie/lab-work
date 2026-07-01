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

from ..config import Config, normalize_header
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

    The record's own lines are the test name followed by an optional priority
    code (e.g. "ST"). Only these last one/two lines matter; any earlier lines are
    report titles/headers picked up before the record and are discarded.

    Priority detection relies on the configured priority_codes list rather than a
    generic "short uppercase token" rule, so short test names like PT / UA / BMP
    are never mistaken for a priority code.
    """
    last = head[-1].strip()
    if len(head) >= 2 and last.upper() in config.text_priority_codes:
        return head[-2].strip(), last
    return last, None


def _strip_patient_headers(
    lines: List[str], config: Config
) -> tuple[List[str], List[Optional[int]]]:
    """Remove patient/encounter header lines; tag each kept line with a patient #.

    When a whole report is pasted, tests are grouped under a patient header like
    "6000788 SURNAME,FIRSTNAME EMERGENCY". Those identifying lines are DISCARDED
    here (never stored), and each remaining line is tagged with an anonymized
    patient number so tests can be attributed to a de-identified patient.

    If there's no MRN + name header, a bare divider line (e.g. "PATIENT", from
    config's patient_delimiters) can also start a new patient.
    """
    pattern = config.text_patient_header_pattern
    delimiters = config.text_patient_delimiters
    kept: List[str] = []
    tags: List[Optional[int]] = []
    current: Optional[int] = None
    for ln in lines:
        is_header = pattern is not None and pattern.search(ln)
        is_delimiter = bool(delimiters) and normalize_header(ln) in delimiters
        if is_header or is_delimiter:
            current = (current or 0) + 1
            continue  # drop the divider/identifying line entirely
        kept.append(ln)
        tags.append(current)
    return kept, tags


def parse_text(text: str, config: Config) -> List[TestRecord]:
    """Parse pasted/plain report text into TestRecords."""
    # Tab-separated pastes -> one field per line, so the line logic below works.
    text = text.replace("\t", "\n")
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    lines, patient_tags = _strip_patient_headers(lines, config)

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
        rec.patient_index = patient_tags[start] if start < len(patient_tags) else None
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
