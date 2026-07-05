"""Configuration loading and header-normalization helpers."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

import yaml

# Canonical fields the rest of the code understands. The config maps each of
# these to a list of header aliases that may appear in a real report.
IDENTITY_FIELDS = ["patient_name", "mrn", "accession"]
TEST_FIELD = "test_name"
TIME_FIELDS = ["order_time", "collected_time", "received_time", "complete_time"]
TAT_FIELDS = [
    "tat_order_to_collected",
    "tat_collected_to_lab",
    "tat_collected_to_complete",
    "tat_lab_to_complete",
    "tat_order_to_complete",
]

# "order_to_received" is a DERIVED-only metric (order → received-in-lab). Reports
# supply the five TAT_FIELDS above; this one is always computed from timestamps
# and is available only for the Daily Summary (not the per-test Detail sheet).
DERIVED_TAT_FIELDS = ["tat_order_to_received"]
# Metrics selectable in daily_summary.metrics = the five report metrics + derived.
DAILY_METRIC_CHOICES = TAT_FIELDS + DERIVED_TAT_FIELDS

# Human-friendly labels for the TAT metrics (used as spreadsheet headers).
TAT_LABELS = {
    "tat_order_to_collected": "Order → Collected",
    "tat_collected_to_lab": "Collected → Lab",
    "tat_collected_to_complete": "Collected → Complete",
    "tat_lab_to_complete": "Lab → Complete",
    "tat_order_to_complete": "Order → Complete",
    "tat_order_to_received": "Order → Received",
}

# Compact labels for the wide "Daily Summary" columns (kept short so a day fits
# on one row).
TAT_SHORT_LABELS = {
    "tat_order_to_collected": "Order→Coll",
    "tat_collected_to_lab": "Coll→Lab",
    "tat_collected_to_complete": "Coll→Comp",
    "tat_lab_to_complete": "Lab→Comp",
    "tat_order_to_complete": "Order→Comp",
    "tat_order_to_received": "Order→Recv",
}

# How each TAT metric is derived from timestamps when the report doesn't supply
# the column directly: metric -> (start_field, end_field).
TAT_FROM_TIMES = {
    "tat_order_to_collected": ("order_time", "collected_time"),
    "tat_collected_to_lab": ("collected_time", "received_time"),
    "tat_collected_to_complete": ("collected_time", "complete_time"),
    "tat_lab_to_complete": ("received_time", "complete_time"),
    "tat_order_to_complete": ("order_time", "complete_time"),
    "tat_order_to_received": ("order_time", "received_time"),
}

DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config",
    "config.yaml",
)


def normalize_header(text: str) -> str:
    """Lower-case and collapse spacing/punctuation so header variants compare equal.

    "Order Date/Time" -> "order date time"
    """
    if text is None:
        return ""
    text = str(text).lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class CategoryRule:
    name: str
    patterns: List[re.Pattern]


@dataclass
class Config:
    raw: Dict[str, Any]
    # canonical field -> set of normalized aliases
    column_aliases: Dict[str, List[str]] = field(default_factory=dict)
    day_start_min: int = 7 * 60
    night_start_min: int = 19 * 60
    day_label: str = "Day"
    night_label: str = "Night"
    shift_basis: str = "collected_time"
    category_rules: List[CategoryRule] = field(default_factory=list)
    default_category: str = "Other"
    # pasted-text layout
    text_datetime_fields: List[str] = field(default_factory=lambda: list(TIME_FIELDS))
    text_tat_fields: List[str] = field(default_factory=lambda: list(TAT_FIELDS))
    text_priority_codes: set = field(default_factory=set)
    text_patient_header_pattern: object = None  # compiled regex or None
    text_patient_delimiters: set = field(default_factory=set)
    # analysis
    tat_cap_minutes: object = None  # float upper cap, or None to disable
    # privacy
    deidentify: bool = True
    include_detail_sheet: bool = True
    include_timestamps: bool = True
    # wide "Daily Summary" layout
    daily_enabled: bool = True
    daily_metrics: List[str] = field(default_factory=list)
    daily_tat_groups: "Dict[str, List[str]]" = field(default_factory=dict)
    daily_shifts: List[str] = field(default_factory=list)
    daily_include_counts: bool = True
    daily_include_patient_count: bool = True
    daily_count_categories: List[str] = field(default_factory=list)  # [] -> derive
    daily_metric_labels: "Dict[str, str]" = field(default_factory=dict)  # header overrides
    daily_overall_label: str = "Overall"

    @property
    def all_fields(self) -> List[str]:
        return IDENTITY_FIELDS + [TEST_FIELD] + TIME_FIELDS + TAT_FIELDS


def _parse_hhmm(value: str, fallback: int) -> int:
    """'07:00' -> minutes since midnight."""
    if not value:
        return fallback
    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*$", str(value))
    if not m:
        return fallback
    return int(m.group(1)) * 60 + int(m.group(2))


def load_config(path: str | None = None) -> Config:
    """Load and validate the YAML config. Falls back to the bundled default."""
    path = path or DEFAULT_CONFIG_PATH
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    cfg = Config(raw=raw)

    # --- columns ---
    cols = raw.get("columns", {}) or {}
    aliases: Dict[str, List[str]] = {}
    for field_name in cfg.all_fields:
        values = cols.get(field_name, []) or []
        aliases[field_name] = [normalize_header(v) for v in values if str(v).strip()]
    cfg.column_aliases = aliases

    # --- shifts ---
    shifts = raw.get("shifts", {}) or {}
    cfg.day_start_min = _parse_hhmm(shifts.get("day_start"), 7 * 60)
    cfg.night_start_min = _parse_hhmm(shifts.get("night_start"), 19 * 60)
    cfg.day_label = shifts.get("day_label", "Day")
    cfg.night_label = shifts.get("night_label", "Night")
    cfg.shift_basis = shifts.get("basis", "collected_time")
    if cfg.shift_basis not in TIME_FIELDS:
        cfg.shift_basis = "collected_time"

    # --- classification ---
    classification = raw.get("classification", {}) or {}
    rules: List[CategoryRule] = []
    for entry in classification.get("categories", []) or []:
        name = entry.get("name")
        if not name:
            continue
        compiled = []
        for pat in entry.get("patterns", []) or []:
            try:
                compiled.append(re.compile(pat, re.IGNORECASE))
            except re.error as exc:
                raise ValueError(
                    f"Invalid regex pattern {pat!r} in category {name!r}: {exc}"
                ) from exc
        rules.append(CategoryRule(name=name, patterns=compiled))
    cfg.category_rules = rules
    cfg.default_category = classification.get("default", "Other")

    # --- pasted-text layout ---
    text_layout = raw.get("text_layout", {}) or {}
    dt_fields = text_layout.get("datetime_fields") or list(TIME_FIELDS)
    cfg.text_datetime_fields = [f for f in dt_fields if f in TIME_FIELDS]
    tat_fields = text_layout.get("tat_fields") or list(TAT_FIELDS)
    cfg.text_tat_fields = [f for f in tat_fields if f in TAT_FIELDS]
    cfg.text_priority_codes = {
        str(c).strip().upper() for c in (text_layout.get("priority_codes") or [])
    }
    header_pat = text_layout.get("patient_header_pattern")
    if header_pat:
        try:
            cfg.text_patient_header_pattern = re.compile(header_pat)
        except re.error as exc:
            raise ValueError(
                f"Invalid patient_header_pattern {header_pat!r}: {exc}"
            ) from exc
    cfg.text_patient_delimiters = {
        normalize_header(d) for d in (text_layout.get("patient_delimiters") or [])
    }

    # --- analysis / outlier cap ---
    analysis = raw.get("analysis", {}) or {}
    cap = analysis.get("tat_cap_minutes", None)
    cfg.tat_cap_minutes = float(cap) if cap not in (None, "", False) else None

    # --- privacy ---
    privacy = raw.get("privacy", {}) or {}
    cfg.deidentify = bool(privacy.get("deidentify", True))
    cfg.include_detail_sheet = bool(privacy.get("include_detail_sheet", True))
    cfg.include_timestamps = bool(privacy.get("include_timestamps", True))

    # --- daily (wide) summary ---
    daily = raw.get("daily_summary", {}) or {}
    cfg.daily_enabled = bool(daily.get("enabled", True))
    metrics = daily.get("metrics") or [
        "tat_order_to_collected",
        "tat_collected_to_lab",
        "tat_lab_to_complete",
        "tat_order_to_complete",
    ]
    cfg.daily_metrics = [m for m in metrics if m in DAILY_METRIC_CHOICES]
    groups = daily.get("tat_groups") or {
        "Blood": ["CBC", "Chemistry", "Cardiac", "Coagulation"],
        "Urine": ["Urinalysis"],
    }
    cfg.daily_tat_groups = {
        str(name): list(cats or []) for name, cats in groups.items()
    }
    cfg.daily_shifts = [str(s) for s in (daily.get("shifts") or ["Day", "Night"])]
    cfg.daily_include_counts = bool(daily.get("include_counts", True))
    cfg.daily_include_patient_count = bool(daily.get("include_patient_count", True))
    cfg.daily_count_categories = [str(c) for c in (daily.get("count_categories") or [])]
    cfg.daily_metric_labels = {
        str(k): str(v) for k, v in (daily.get("metric_labels") or {}).items()
    }
    cfg.daily_overall_label = str(daily.get("overall_label", "Overall"))

    return cfg
