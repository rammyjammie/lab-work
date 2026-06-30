from datetime import datetime

from cerner_tat.classify import assign_shift, classify_category
from cerner_tat.config import load_config
from cerner_tat.models import TestRecord

CFG = load_config()


def test_categories():
    cases = {
        "CBC W/ DIFF": "CBC",
        "Complete Blood Count": "CBC",
        "BMP": "Chemistry",
        "CMP": "Chemistry",
        "Basic Metabolic Panel": "Chemistry",
        "Troponin I": "Cardiac",
        "BNP": "Cardiac",
        "NT-proBNP": "Cardiac",
        "PT/INR": "Coagulation",
        "PTT": "Coagulation",
        "aPTT": "Coagulation",
        "D-Dimer": "Coagulation",
        "Urinalysis, Auto": "Urinalysis",
        "Random Send-Out Test": "Other",
    }
    for name, expected in cases.items():
        assert classify_category(name, CFG) == expected, name


def test_pt_does_not_match_ptt():
    # \bpt\b must match standalone PT but not PTT (which is Coagulation anyway)
    assert classify_category("PT", CFG) == "Coagulation"
    assert classify_category("PTT", CFG) == "Coagulation"


def test_shift_day_night_boundaries():
    def rec(hour, minute=0):
        r = TestRecord(test_name="x")
        r.collected_time = datetime(2026, 6, 29, hour, minute)
        return r

    assert assign_shift(rec(7, 0), CFG) == "Day"      # exactly 07:00 -> Day
    assert assign_shift(rec(12), CFG) == "Day"
    assert assign_shift(rec(18, 59), CFG) == "Day"
    assert assign_shift(rec(19, 0), CFG) == "Night"   # exactly 19:00 -> Night
    assert assign_shift(rec(23), CFG) == "Night"
    assert assign_shift(rec(3), CFG) == "Night"
    assert assign_shift(rec(6, 59), CFG) == "Night"


def test_shift_missing_basis_is_none():
    r = TestRecord(test_name="x")  # no collected_time
    assert assign_shift(r, CFG) is None
