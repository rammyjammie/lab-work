"""Tests for the PATIENT divider line and the TAT outlier cap."""

from cerner_tat.aggregate import build_summaries
from cerner_tat.classify import deidentify, enrich
from cerner_tat.config import TAT_LABELS, load_config
from cerner_tat.parsers import parse_text

CFG = load_config()

# Two patients separated only by bare "PATIENT" divider lines (no MRN/name).
# The second patient's Urine Culture takes ~3000 minutes.
PASTE = """PATIENT
Urinalysis, Auto
ST
06/17/2026 08:00
06/17/2026 08:10
06/17/2026 08:10
06/17/2026 08:40
10
0
30
30
40
PATIENT
Urine Culture
ST
06/17/2026 08:00
06/17/2026 08:15
06/17/2026 08:15
06/19/2026 10:15
15
0
3000
3000
3015"""


def _records(cfg=CFG):
    return deidentify(enrich(parse_text(PASTE, cfg), cfg), cfg)


def test_patient_delimiter_splits_patients():
    recs = _records()
    assert len(recs) == 2
    assert [r.patient_index for r in recs] == [1, 2]
    # the word "PATIENT" is never a test name
    assert all(r.test_name != "PATIENT" for r in recs)


def test_delimiter_line_not_counted_as_test():
    recs = _records()
    assert {r.test_name for r in recs} == {"Urinalysis, Auto", "Urine Culture"}


def test_cap_excludes_outlier_from_average():
    recs = _records()
    s = build_summaries(recs, CFG)
    col = TAT_LABELS["tat_collected_to_complete"] + " (min)"
    ua = s.tat_by_type[s.tat_by_type["Category"] == "Urinalysis"].iloc[0]
    # both UA tests counted, but the 3000-min value is excluded -> avg = 30
    assert ua["N"] == 2
    assert ua[col] == 30.0


def test_cap_keeps_small_values():
    recs = _records()
    s = build_summaries(recs, CFG)
    col = TAT_LABELS["tat_order_to_collected"] + " (min)"
    ua = s.tat_by_type[s.tat_by_type["Category"] == "Urinalysis"].iloc[0]
    # 10 and 15 are both under the cap -> averaged normally
    assert ua[col] == 12.5


def test_summary_reports_excluded_count():
    recs = _records()
    s = build_summaries(recs, CFG)
    row = s.summary[s.summary["Metric"].str.startswith("TAT values excluded")]
    assert not row.empty
    # coll->complete, lab->complete, order->complete all exceed 500
    assert row.iloc[0]["Value"] == "3"


def test_detail_keeps_raw_outlier_value():
    recs = _records()
    s = build_summaries(recs, CFG)
    col = TAT_LABELS["tat_collected_to_complete"] + " (min)"
    assert 3000 in list(s.detail[col])  # raw value preserved on Detail sheet


def test_cap_disabled_includes_outlier():
    cfg = load_config()
    cfg.tat_cap_minutes = None
    recs = _records(cfg)
    s = build_summaries(recs, cfg)
    col = TAT_LABELS["tat_collected_to_complete"] + " (min)"
    ua = s.tat_by_type[s.tat_by_type["Category"] == "Urinalysis"].iloc[0]
    assert ua[col] == 1515.0  # (30 + 3000) / 2
