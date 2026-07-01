"""Tests for patient-header stripping and de-identification."""

from cerner_tat.aggregate import build_summaries
from cerner_tat.classify import deidentify, enrich
from cerner_tat.config import load_config
from cerner_tat.parsers import parse_text

CFG = load_config()

# A whole-report paste grouped by patient header lines.
MASS_PASTE = """6000788 SMITH,JOHN EMERGENCY
PT
ST
06/17/2026 07:54
06/17/2026 08:06
06/17/2026 08:06
06/17/2026 08:21
12
0
15
15
27
CBC w/ Diff
ST
06/17/2026 07:49
06/17/2026 08:06
06/17/2026 08:06
06/17/2026 08:13
16
0
6
7
23
6000799 DOE,JANE EMERGENCY
Troponin I
ST
06/17/2026 20:10
06/17/2026 20:20
06/17/2026 20:20
06/17/2026 20:45
10
0
25
25
35
6000801 O'BRIEN,PAT ICU
Comprehensive Metabolic Panel
ST
06/17/2026 21:00
06/17/2026 21:15
06/17/2026 21:15
06/17/2026 22:30
15
0
75
75
90"""

NAMES_AND_MRNS = ["SMITH", "DOE", "BRIEN", "JOHN", "JANE", "PAT",
                  "6000788", "6000799", "6000801"]


def _records():
    return deidentify(enrich(parse_text(MASS_PASTE, CFG), CFG), CFG)


def test_headers_stripped_tests_survive():
    recs = _records()
    assert len(recs) == 4
    names = [r.test_name for r in recs]
    assert names == ["PT", "CBC w/ Diff", "Troponin I", "Comprehensive Metabolic Panel"]


def test_no_identifiers_stored_on_records():
    for r in _records():
        assert r.patient_name is None
        assert r.mrn is None
        assert r.accession is None
        blob = f"{r.test_name} {r.raw}"
        for token in NAMES_AND_MRNS:
            assert token not in blob


def test_patient_grouping_anonymized():
    recs = _records()
    # First two tests share patient 1; then patient 2, patient 3
    assert [r.patient_index for r in recs] == [1, 1, 2, 3]
    assert [r.patient_label for r in recs][:2] == ["Patient 1", "Patient 1"]


def test_no_phi_anywhere_in_workbook_frames():
    recs = _records()
    s = build_summaries(recs, CFG)
    for frame in (s.detail, s.summary, s.counts_by_type, s.tat_by_type, s.tat_by_type_shift):
        blob = frame.to_csv(index=False)
        for token in NAMES_AND_MRNS:
            assert token not in blob


def test_summary_reports_distinct_patients():
    recs = _records()
    s = build_summaries(recs, CFG)
    row = s.summary[s.summary["Metric"] == "Distinct patients"]
    assert not row.empty
    assert row.iloc[0]["Value"] == "3"


def test_deidentify_off_keeps_grouping_but_still_no_names():
    # Even with de-id disabled, the text parser never captured names to begin
    # with, so patient_index remains the only patient info.
    cfg = load_config()
    cfg.deidentify = False
    recs = deidentify(enrich(parse_text(MASS_PASTE, cfg), cfg), cfg)
    assert [r.patient_index for r in recs] == [1, 1, 2, 3]
    assert all(r.patient_name is None for r in recs)


def test_shift_split_across_patients():
    recs = _records()
    shifts = {r.test_name: r.shift for r in recs}
    assert shifts["PT"] == "Day"
    assert shifts["Troponin I"] == "Night"       # collected 20:20
    assert shifts["Comprehensive Metabolic Panel"] == "Night"  # collected 21:15
