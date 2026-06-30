import os

import pandas as pd

from cerner_tat.aggregate import build_summaries
from cerner_tat.classify import enrich
from cerner_tat.config import load_config
from cerner_tat.parsers import parse_file
from cerner_tat.pipeline import process_file

SAMPLE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "samples",
    "example_report.html",
)
CFG = load_config()


def test_parses_all_rows():
    records = parse_file(SAMPLE, CFG)
    assert len(records) == 13


def test_enrichment_assigns_category_and_shift():
    records = enrich(parse_file(SAMPLE, CFG), CFG)
    assert all(r.category for r in records)
    assert all(r.shift in ("Day", "Night") for r in records)
    # 7 day, 6 night from the synthetic data
    assert sum(r.shift == "Day" for r in records) == 7
    assert sum(r.shift == "Night" for r in records) == 6


def test_direct_tat_matches_computed():
    # The sample provides direct TAT columns; computing from timestamps must agree.
    records = enrich(parse_file(SAMPLE, CFG), CFG)
    for r in records:
        computed = (r.complete_time - r.order_time).total_seconds() / 60.0
        assert abs(r.tat_order_to_complete - computed) < 1e-6


def test_category_counts():
    records = enrich(parse_file(SAMPLE, CFG), CFG)
    counts = {}
    for r in records:
        counts[r.category] = counts.get(r.category, 0) + 1
    assert counts["CBC"] == 2
    assert counts["Cardiac"] == 3      # 2x Troponin + 1 BNP
    assert counts["Coagulation"] == 3  # PT/INR, PTT, D-Dimer
    assert counts["Chemistry"] == 3    # BMP + 2x CMP
    assert counts["Urinalysis"] == 2


def test_summaries_build():
    records = enrich(parse_file(SAMPLE, CFG), CFG)
    s = build_summaries(records, CFG)
    assert not s.detail.empty
    assert not s.tat_by_type.empty
    assert "N" in s.tat_by_type.columns
    # All-types row present
    assert (s.tat_by_type["Category"] == "All Types").any()


def test_process_file_writes_xlsx(tmp_path):
    result = process_file(SAMPLE, str(tmp_path), CFG)
    assert result.error is None
    assert result.record_count == 13
    assert os.path.exists(result.output_path)
    # sheets are readable
    xls = pd.ExcelFile(result.output_path)
    for sheet in ["Summary", "Counts by Type", "TAT by Type", "TAT by Type & Shift", "Detail"]:
        assert sheet in xls.sheet_names
