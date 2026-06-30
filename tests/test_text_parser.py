"""Tests for the pasted-text parser, using the real sample layout."""

import os
from datetime import datetime

from cerner_tat.classify import enrich
from cerner_tat.config import load_config
from cerner_tat.parsers import parse_text, parse_text_file

CFG = load_config()
SAMPLE_TXT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "samples",
    "example_pasted_report.txt",
)


def test_parses_six_records():
    recs = parse_text_file(SAMPLE_TXT, CFG)
    assert len(recs) == 6


def test_field_mapping_first_record():
    recs = enrich(parse_text_file(SAMPLE_TXT, CFG), CFG)
    pt = recs[0]
    assert pt.test_name == "PT"
    assert pt.raw.get("priority") == "ST"
    assert pt.order_time == datetime(2026, 6, 17, 7, 54)
    assert pt.collected_time == datetime(2026, 6, 17, 8, 6)
    assert pt.received_time == datetime(2026, 6, 17, 8, 6)
    assert pt.complete_time == datetime(2026, 6, 17, 8, 21)
    assert pt.tat_order_to_collected == 12
    assert pt.tat_collected_to_lab == 0
    assert pt.tat_collected_to_complete == 15
    assert pt.tat_lab_to_complete == 15
    assert pt.tat_order_to_complete == 27


def test_tat_values_close_to_timestamps():
    # Cerner shows minute-truncated timestamps but computes TAT on the underlying
    # seconds, so the reported value can differ from a minute-only recompute by
    # up to ~1 minute. The reported value (used by the tool) is authoritative.
    recs = enrich(parse_text_file(SAMPLE_TXT, CFG), CFG)
    for r in recs:
        recomputed = (r.collected_time - r.order_time).total_seconds() / 60
        assert abs(r.tat_order_to_collected - recomputed) <= 1
        recomputed_oc = (r.complete_time - r.order_time).total_seconds() / 60
        assert abs(r.tat_order_to_complete - recomputed_oc) <= 1


def test_negative_tat_preserved():
    recs = enrich(parse_text_file(SAMPLE_TXT, CFG), CFG)
    istat = [r for r in recs if "iSTAT" in r.test_name][0]
    assert istat.tat_order_to_collected == -7  # order logged after collection


def test_categories():
    recs = enrich(parse_text_file(SAMPLE_TXT, CFG), CFG)
    by_name = {r.test_name: r.category for r in recs}
    assert by_name["PT"] == "Coagulation"
    assert by_name["PTT"] == "Coagulation"
    assert by_name["CBC w/ Diff"] == "CBC"
    assert by_name["Automated Diff"] == "CBC"
    assert by_name["Comprehensive Metabolic Panel"] == "Chemistry"
    assert by_name["Basic Metabolic Panel iSTAT"] == "Chemistry"


def test_all_day_shift():
    recs = enrich(parse_text_file(SAMPLE_TXT, CFG), CFG)
    assert all(r.shift == "Day" for r in recs)  # all collected ~08:06


def test_ignores_leading_title_lines():
    text = (
        "Laboratory Turnaround Time Report\n"
        "Run date 06/17/2026\n"
        "PT\nST\n"
        "06/17/2026 07:54\n06/17/2026 08:06\n06/17/2026 08:06\n06/17/2026 08:21\n"
        "12\n0\n15\n15\n27\n"
    )
    recs = parse_text(text, CFG)
    assert len(recs) == 1
    assert recs[0].test_name == "PT"
