"""Assign each record a test category and a shift."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from .config import TAT_FIELDS, TAT_FROM_TIMES, Config
from .models import TestRecord


def classify_category(test_name: str, config: Config) -> str:
    """Return the category for a test name using the configured rules (first match)."""
    name = test_name or ""
    for rule in config.category_rules:
        for pattern in rule.patterns:
            if pattern.search(name):
                return rule.name
    return config.default_category


def assign_shift(record: TestRecord, config: Config) -> Optional[str]:
    """Day vs Night based on the configured basis timestamp.

    Day is [day_start, night_start); everything else is Night. Returns None if
    the basis timestamp is missing (can't tell which shift).
    """
    ts: Optional[datetime] = getattr(record, config.shift_basis, None)
    if ts is None:
        return None
    minutes = ts.hour * 60 + ts.minute
    start, end = config.day_start_min, config.night_start_min
    if start <= end:
        is_day = start <= minutes < end
    else:
        # handles an inverted window if someone configures it that way
        is_day = minutes >= start or minutes < end
    return config.day_label if is_day else config.night_label


def _ensure_tat(record: TestRecord) -> None:
    """Fill any missing TAT metric from timestamps, in minutes."""
    for metric, (start_field, end_field) in TAT_FROM_TIMES.items():
        if getattr(record, metric) is not None:
            continue
        start = getattr(record, start_field)
        end = getattr(record, end_field)
        if start is not None and end is not None:
            delta = (end - start).total_seconds() / 60.0
            setattr(record, metric, delta)


def enrich(records: Iterable[TestRecord], config: Config) -> list[TestRecord]:
    """Classify category + shift and compute any missing TAT values, in place."""
    out = []
    for rec in records:
        rec.category = classify_category(rec.test_name, config)
        rec.shift = assign_shift(rec, config)
        _ensure_tat(rec)
        out.append(rec)
    return out
