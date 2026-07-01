"""Tests for the network kill-switch and the fail-closed PHI guard."""

import socket

import pandas as pd
import pytest

import cerner_tat  # noqa: F401 — importing installs the network guard
from cerner_tat.config import load_config
from cerner_tat.security import (
    NetworkBlocked,
    PhiLeakError,
    assert_no_phi,
    install_network_guard,
    scan_frame_for_phi,
)

CFG = load_config()


# --- network kill-switch ---------------------------------------------------

def test_guard_is_installed():
    assert install_network_guard() is True


def test_outbound_tcp_blocked():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(NetworkBlocked):
        s.connect(("8.8.8.8", 53))


def test_dns_blocked():
    with pytest.raises(NetworkBlocked):
        socket.getaddrinfo("example.com", 80)


def test_create_connection_blocked():
    with pytest.raises(NetworkBlocked):
        socket.create_connection(("1.1.1.1", 443), timeout=1)


# --- PHI guard -------------------------------------------------------------

def test_clean_output_passes():
    df = pd.DataFrame(
        {"Patient": ["Patient 1"], "Test": ["Urinalysis, Auto"], "Coll→Comp (min)": [30]}
    )
    assert scan_frame_for_phi(df, CFG) == []
    assert_no_phi([df], CFG)  # must not raise


def test_test_name_with_comma_not_flagged():
    # legitimate test names containing a comma must not trip the guard
    for name in ["Urinalysis, Auto", "Basic Metabolic Panel, iSTAT", "PT/INR"]:
        df = pd.DataFrame({"Test": [name]})
        assert scan_frame_for_phi(df, CFG) == []


def test_leaked_mrn_name_in_test_column_caught():
    df = pd.DataFrame({"Test": ["6000788 SMITH,JOHN EMERGENCY"]})
    with pytest.raises(PhiLeakError):
        assert_no_phi([df], CFG)


def test_leaked_name_in_identity_column_caught():
    df = pd.DataFrame({"Patient": ["SMITH,JOHN"]})
    with pytest.raises(PhiLeakError):
        assert_no_phi([df], CFG)


def test_guard_skipped_when_deidentify_off():
    cfg = load_config()
    cfg.deidentify = False
    df = pd.DataFrame({"Patient": ["SMITH,JOHN"], "Test": ["6000788 DOE,JANE ER"]})
    assert_no_phi([df], cfg)  # opted into identifiers -> no error


def test_large_tat_value_not_mistaken_for_mrn():
    # a 14400-minute (10-day) culture must not look like an MRN
    df = pd.DataFrame({"Test": ["Urine Culture"], "Coll→Comp (min)": [14400]})
    assert scan_frame_for_phi(df, CFG) == []


# --- data minimization -----------------------------------------------------

_PASTE = """CBC w/ Diff
ST
06/17/2026 07:49
06/17/2026 08:06
06/17/2026 08:06
06/17/2026 08:13
16
0
6
7
23"""


def _summaries(cfg):
    from cerner_tat.aggregate import build_summaries
    from cerner_tat.classify import deidentify, enrich
    from cerner_tat.parsers import parse_text

    recs = deidentify(enrich(parse_text(_PASTE, cfg), cfg), cfg)
    return build_summaries(recs, cfg)


def test_include_timestamps_off_drops_time_columns():
    cfg = load_config()
    cfg.include_timestamps = False
    s = _summaries(cfg)
    for col in ("Ordered", "Collected", "Received", "Completed"):
        assert col not in s.detail.columns
    # TAT and identity-free columns remain
    assert "Test" in s.detail.columns


def test_include_detail_sheet_off_empties_detail():
    cfg = load_config()
    cfg.include_detail_sheet = False
    s = _summaries(cfg)
    assert s.detail.empty
    # the averaged sheets are still produced
    assert not s.tat_by_type.empty
