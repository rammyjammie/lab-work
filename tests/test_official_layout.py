"""Tests for the official_layout.yaml preset (the boss's requested columns)."""

import os

from cerner_tat.aggregate import build_daily_summary
from cerner_tat.classify import deidentify, enrich
from cerner_tat.config import load_config
from cerner_tat.parsers import parse_text

PRESET = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "official_layout.yaml",
)
CFG = load_config(PRESET)

PASTE = """Troponin I
ST
06/17/2026 07:54
06/17/2026 08:06
06/17/2026 08:10
06/17/2026 08:40
12
4
34
30
46
D-Dimer
ST
06/17/2026 08:00
06/17/2026 08:05
06/17/2026 08:09
06/17/2026 08:20
5
4
15
11
20
Lactate
ST
06/17/2026 08:00
06/17/2026 08:05
06/17/2026 08:09
06/17/2026 08:20
5
4
15
11
20
PT/INR
ST
06/17/2026 08:00
06/17/2026 08:05
06/17/2026 08:09
06/17/2026 08:20
5
4
15
11
20
Urinalysis, Auto
ST
06/17/2026 21:00
06/17/2026 21:10
06/17/2026 21:15
06/17/2026 21:45
10
5
35
30
45
PTT
ST
06/17/2026 08:00
06/17/2026 08:05
06/17/2026 08:09
06/17/2026 08:30
5
4
25
21
30"""


def _records():
    return deidentify(enrich(parse_text(PASTE, CFG), CFG), CFG)


def test_analyte_classification():
    by = {r.test_name: r.category for r in _records()}
    assert by["Troponin I"] == "Trop"
    assert by["D-Dimer"] == "D-dimer"
    assert by["Lactate"] == "Lactate"
    assert by["PT/INR"] == "PT"
    assert by["Urinalysis, Auto"] == "UA"
    # PTT is not one of the boss's categories -> Other (documented)
    assert by["PTT"] == "Other"


def test_order_to_received_metric():
    r = [x for x in _records() if x.test_name == "Troponin I"][0]
    # ordered 07:54, received 08:10 -> 16 minutes
    assert r.tat_order_to_received == 16.0


def test_expected_columns_present():
    d = build_daily_summary(_records(), CFG)
    cols = list(d.columns)
    # count columns in the boss's order
    assert cols[:8] == ["Date", "CBC", "Chem", "D-dimer", "Lactate", "PT", "Trop", "UA"]
    assert "Total" in cols and "Patients" in cols
    # TAT: 2 groups x 3 metrics x 3 shifts = 18
    tat_cols = [c for c in cols if "→" in c]
    assert len(tat_cols) == 18
    for shift in ("Overall", "Dayshift", "Nights"):
        assert f"Trop order→receive ({shift})" in cols
        assert f"UA receive→result ({shift})" in cols


def test_order_to_result_is_sum_of_phases():
    d = build_daily_summary(_records(), CFG).iloc[0]
    # Troponin is the only Trop test, on Dayshift
    recv = d["Trop order→receive (Dayshift)"]
    result = d["Trop receive→result (Dayshift)"]
    total = d["Trop order→result (Dayshift)"]
    assert total == recv + result  # the redundant column, proven redundant


# --- recommended (lean) preset ---------------------------------------------

_RECOMMENDED = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "recommended_layout.yaml",
)


def test_recommended_preset_is_trimmed():
    cfg = load_config(_RECOMMENDED)
    recs = deidentify(enrich(parse_text(PASTE, cfg), cfg), cfg)
    cols = list(build_daily_summary(recs, cfg).columns)
    tat_cols = [c for c in cols if "→" in c]
    # 2 groups x 2 metrics x 2 shifts = 8 (down from 18)
    assert len(tat_cols) == 8
    # no redundant total metric and no Overall shift
    assert not any("order→result" in c for c in cols)
    assert not any("(Overall)" in c for c in cols)
    # same counts as the official preset
    assert cols[:8] == ["Date", "CBC", "Chem", "D-dimer", "Lactate", "PT", "Trop", "UA"]
