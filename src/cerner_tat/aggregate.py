"""Turn a list of enriched records into the summary tables we write to Excel."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

from .config import TAT_FIELDS, TAT_LABELS, TAT_SHORT_LABELS, Config
from .models import TestRecord


@dataclass
class Summaries:
    detail: pd.DataFrame
    counts_by_type: pd.DataFrame
    tat_by_type: pd.DataFrame
    tat_by_type_shift: pd.DataFrame
    summary: pd.DataFrame
    daily: pd.DataFrame


def _detail_frame(records: List[TestRecord]) -> pd.DataFrame:
    rows = [r.to_row() for r in records]
    df = pd.DataFrame(rows)
    # Drop identity columns that are entirely empty (e.g. MRN/Accession after
    # de-identification, or Patient when the report had no patient grouping).
    for col in ("patient", "mrn", "accession"):
        if col in df.columns and df[col].isna().all():
            df = df.drop(columns=[col])
    # rename to friendly headers
    rename = {
        "patient": "Patient",
        "mrn": "MRN",
        "accession": "Accession",
        "test_name": "Test",
        "category": "Category",
        "shift": "Shift",
        "order_time": "Ordered",
        "collected_time": "Collected",
        "received_time": "Received",
        "complete_time": "Completed",
    }
    rename.update({k: TAT_LABELS[k] + " (min)" for k in TAT_FIELDS})
    return df.rename(columns=rename)


def _counts_by_type(df: pd.DataFrame, config: Config) -> pd.DataFrame:
    """Category x Shift counts with row/column totals."""
    if df.empty:
        return pd.DataFrame()
    pivot = pd.pivot_table(
        df,
        index="Category",
        columns="Shift",
        values="Test",
        aggfunc="count",
        fill_value=0,
        margins=True,
        margins_name="Total",
    )
    # keep shift columns in a stable order: Day, Night, (None), Total
    preferred = [config.day_label, config.night_label]
    cols = [c for c in preferred if c in pivot.columns]
    cols += [c for c in pivot.columns if c not in preferred and c != "Total"]
    if "Total" in pivot.columns:
        cols.append("Total")
    return pivot[cols].reset_index()


def _mask_outliers(df: pd.DataFrame, cap) -> pd.DataFrame:
    """Return a copy of the detail frame with TAT values > cap set to NaN.

    Used only for the AVERAGED sheets — the Detail sheet keeps the real values.
    """
    if cap is None or df.empty:
        return df
    masked = df.copy()
    tat_cols = [TAT_LABELS[k] + " (min)" for k in TAT_FIELDS if TAT_LABELS[k] + " (min)" in df.columns]
    for col in tat_cols:
        masked.loc[masked[col] > cap, col] = pd.NA
        masked[col] = pd.to_numeric(masked[col], errors="coerce")
    return masked


def _tat_by_type(df: pd.DataFrame) -> pd.DataFrame:
    """Average of each TAT metric per category (plus an All-types row)."""
    if df.empty:
        return pd.DataFrame()
    tat_cols = [TAT_LABELS[k] + " (min)" for k in TAT_FIELDS]
    present = [c for c in tat_cols if c in df.columns]
    grouped = df.groupby("Category")[present].mean().round(1)

    # count column for context
    counts = df.groupby("Category")["Test"].count().rename("N")
    grouped.insert(0, "N", counts)

    overall = df[present].mean().round(1)
    overall["N"] = len(df)
    grouped.loc["All Types"] = overall
    out = grouped.reset_index()
    out["N"] = out["N"].astype(int)
    return out


def _tat_by_type_shift(df: pd.DataFrame) -> pd.DataFrame:
    """Average of each TAT metric per category AND shift."""
    if df.empty:
        return pd.DataFrame()
    tat_cols = [TAT_LABELS[k] + " (min)" for k in TAT_FIELDS]
    present = [c for c in tat_cols if c in df.columns]
    grouped = (
        df.groupby(["Category", "Shift"], dropna=False)[present]
        .mean()
        .round(1)
    )
    counts = (
        df.groupby(["Category", "Shift"], dropna=False)["Test"]
        .count()
        .rename("N")
    )
    grouped.insert(0, "N", counts)
    out = grouped.reset_index()
    out["N"] = out["N"].astype(int)
    return out


def _summary_frame(
    df: pd.DataFrame, records: List[TestRecord], config: Config
) -> pd.DataFrame:
    """A compact at-a-glance table."""
    if df.empty:
        return pd.DataFrame({"Metric": ["Total tests"], "Value": ["0"]})

    # Values are kept as strings so the blank spacer row stays blank (not NaN)
    # and counts render as "13" rather than "13.0".
    rows = [("Total tests", str(len(df)))]
    patient_count = len({r.patient_index for r in records if r.patient_index is not None})
    if patient_count:
        rows.append(("Distinct patients", str(patient_count)))
    cap = config.tat_cap_minutes
    if cap is not None:
        excluded = sum(
            1
            for r in records
            for m in TAT_FIELDS
            if getattr(r, m) is not None and getattr(r, m) > cap
        )
        if excluded:
            rows.append((f"TAT values excluded (> {cap:g} min)", str(excluded)))
    for shift in [config.day_label, config.night_label]:
        rows.append((f"Tests — {shift} shift", str(int((df["Shift"] == shift).sum()))))
    missing_shift = int(df["Shift"].isna().sum())
    if missing_shift:
        rows.append(("Tests — shift unknown", str(missing_shift)))

    rows.append(("", ""))
    for category, n in df["Category"].value_counts().items():
        rows.append((f"Tests — {category}", str(int(n))))

    return pd.DataFrame(rows, columns=["Metric", "Value"])


def _report_date(records: List[TestRecord]) -> Optional[str]:
    """The report's date = the most common collection date across records."""
    dates = []
    for r in records:
        ts = r.collected_time or r.order_time or r.complete_time
        if ts is not None:
            dates.append(ts.date())
    if not dates:
        return None
    return Counter(dates).most_common(1)[0][0].isoformat()


def _avg(records: List[TestRecord], metric: str, cap=None) -> Optional[float]:
    vals = [
        v
        for v in (getattr(r, metric) for r in records)
        if v is not None and (cap is None or v <= cap)
    ]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 1)


def _daily_category_order(records: List[TestRecord], config: Config) -> List[str]:
    """Count-column order: the grouped categories first, then any extras seen."""
    ordered: List[str] = []
    for cats in config.daily_tat_groups.values():
        for c in cats:
            if c not in ordered:
                ordered.append(c)
    for r in records:
        if r.category and r.category not in ordered:
            ordered.append(r.category)
    return ordered


def build_daily_summary(records: List[TestRecord], config: Config) -> pd.DataFrame:
    """One wide row per report: counts + patient count + grouped TAT by shift.

    Column order (all driven by config.daily_*):
      Date | <per-type counts> | Total | Patients | <group·metric·shift TATs…>
    """
    row: dict = {"Date": _report_date(records) or ""}

    if config.daily_include_counts:
        counts = Counter(r.category for r in records if r.category)
        for cat in _daily_category_order(records, config):
            row[cat] = counts.get(cat, 0)
        row["Total"] = len(records)

    if config.daily_include_patient_count:
        row["Patients"] = len(
            {r.patient_index for r in records if r.patient_index is not None}
        )

    for shift in config.daily_shifts:
        shift_recs = (
            records if shift == "Overall" else [r for r in records if r.shift == shift]
        )
        for group, cats in config.daily_tat_groups.items():
            catset = set(cats)
            grp = [r for r in shift_recs if r.category in catset]
            for metric in config.daily_metrics:
                col = f"{group} {TAT_SHORT_LABELS[metric]} ({shift})"
                row[col] = _avg(grp, metric, config.tat_cap_minutes)

    return pd.DataFrame([row])


def build_summaries(records: List[TestRecord], config: Config) -> Summaries:
    detail = _detail_frame(records)
    masked = _mask_outliers(detail, config.tat_cap_minutes)  # for averages only
    return Summaries(
        detail=detail,
        counts_by_type=_counts_by_type(detail, config),
        tat_by_type=_tat_by_type(masked),
        tat_by_type_shift=_tat_by_type_shift(masked),
        summary=_summary_frame(detail, records, config),
        daily=build_daily_summary(records, config) if config.daily_enabled else pd.DataFrame(),
    )
