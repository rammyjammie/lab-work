"""Tests for the wide Daily Summary row and the running master workbook."""

import os

import pandas as pd

from cerner_tat.aggregate import build_daily_summary
from cerner_tat.classify import deidentify, enrich
from cerner_tat.config import load_config
from cerner_tat.parsers import parse_text
from cerner_tat.report import append_to_master

CFG = load_config()

PASTE = """6000788 SMITH,JOHN EMERGENCY
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
Urinalysis, Auto
ST
06/17/2026 09:00
06/17/2026 09:10
06/17/2026 09:10
06/17/2026 09:40
10
0
30
30
40"""


def _daily():
    recs = deidentify(enrich(parse_text(PASTE, CFG), CFG), CFG)
    return build_daily_summary(recs, CFG).iloc[0]


def test_column_count_and_order():
    row = _daily()
    cols = list(row.index)
    # Date + 5 counts + Total + Patients + (4 metrics x 2 groups x 2 shifts = 16)
    assert len(cols) == 1 + 5 + 1 + 1 + 16
    assert cols[0] == "Date"
    assert cols[1:6] == ["CBC", "Chemistry", "Cardiac", "Coagulation", "Urinalysis"]
    assert cols[6] == "Total"
    assert cols[7] == "Patients"


def test_counts_and_date():
    row = _daily()
    assert row["Date"] == "2026-06-17"
    assert row["CBC"] == 1
    assert row["Cardiac"] == 1
    assert row["Urinalysis"] == 1
    assert row["Total"] == 3


def test_blood_vs_urine_grouping():
    row = _daily()
    # CBC (day) is the only Blood-Day test -> its values populate Blood Day cols
    assert row["Blood Order→Coll (Day)"] == 16
    assert row["Blood Lab→Comp (Day)"] == 7
    # Urinalysis (09:10 collected) is Day -> populates Urine Day cols
    assert row["Urine Order→Coll (Day)"] == 10
    assert row["Urine Lab→Comp (Day)"] == 30
    # Troponin at 20:20 is the only Blood-Night test
    assert row["Blood Order→Comp (Night)"] == 35


def test_total_is_sum_of_phases():
    row = _daily()
    # order->complete should equal the three independent phases summed
    phases = (
        row["Blood Order→Coll (Day)"]
        + row["Blood Coll→Lab (Day)"]
        + row["Blood Lab→Comp (Day)"]
    )
    assert row["Blood Order→Comp (Day)"] == phases


def test_master_append_creates_and_grows(tmp_path):
    recs = deidentify(enrich(parse_text(PASTE, CFG), CFG), CFG)
    daily = build_daily_summary(recs, CFG)
    master = str(tmp_path / "master.xlsx")

    append_to_master(daily, master)
    assert os.path.exists(master)
    df1 = pd.read_excel(master, sheet_name="Master")
    assert len(df1) == 1

    append_to_master(daily, master)
    df2 = pd.read_excel(master, sheet_name="Master")
    assert len(df2) == 2
    assert list(df1.columns) == list(df2.columns)


def test_master_no_phi(tmp_path):
    recs = deidentify(enrich(parse_text(PASTE, CFG), CFG), CFG)
    daily = build_daily_summary(recs, CFG)
    master = str(tmp_path / "master.xlsx")
    append_to_master(daily, master)
    blob = pd.read_excel(master, sheet_name="Master").to_csv(index=False)
    for token in ["SMITH", "JOHN", "6000788"]:
        assert token not in blob


MULTI_DATE = """CBC w/ Diff
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
Comprehensive Metabolic Panel
ST
06/18/2026 09:00
06/18/2026 09:12
06/18/2026 09:12
06/18/2026 10:30
12
0
78
78
90"""


def test_one_row_per_date():
    recs = deidentify(enrich(parse_text(MULTI_DATE, CFG), CFG), CFG)
    d = build_daily_summary(recs, CFG)
    assert len(d) == 2
    assert list(d["Date"]) == ["2026-06-17", "2026-06-18"]
    # counts land on the right day
    r17 = d[d["Date"] == "2026-06-17"].iloc[0]
    r18 = d[d["Date"] == "2026-06-18"].iloc[0]
    assert r17["CBC"] == 1 and r17["Total"] == 1
    assert r18["Chemistry"] == 1 and r18["Total"] == 1


def test_master_append_grows_by_row_count(tmp_path):
    recs = deidentify(enrich(parse_text(MULTI_DATE, CFG), CFG), CFG)
    d = build_daily_summary(recs, CFG)
    master = str(tmp_path / "m.xlsx")
    append_to_master(d, master)
    df = pd.read_excel(master, sheet_name="Master")
    assert len(df) == 2  # both dates appended


def test_disabled_produces_empty_daily():
    cfg = load_config()
    cfg.daily_enabled = False
    from cerner_tat.aggregate import build_summaries

    recs = deidentify(enrich(parse_text(PASTE, cfg), cfg), cfg)
    s = build_summaries(recs, cfg)
    assert s.daily.empty
