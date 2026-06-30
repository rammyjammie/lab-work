from datetime import datetime

from cerner_tat.parsers.base import parse_duration_minutes, parse_timestamp


def test_duration_plain_minutes():
    assert parse_duration_minutes("83") == 83.0
    assert parse_duration_minutes("83.5") == 83.5


def test_duration_hms():
    assert parse_duration_minutes("1:23") == 83.0
    assert parse_duration_minutes("01:23:30") == 83.5


def test_duration_tokens():
    assert parse_duration_minutes("1h 23m") == 83.0
    assert parse_duration_minutes("45m") == 45.0
    assert parse_duration_minutes("1d 0h 0m") == 1440.0


def test_duration_pandas_delta():
    assert parse_duration_minutes("0 days 01:23:00") == 83.0


def test_duration_empty():
    for v in (None, "", "  ", "N/A", "-"):
        assert parse_duration_minutes(v) is None


def test_timestamp_formats():
    assert parse_timestamp("2026-06-29 08:15") == datetime(2026, 6, 29, 8, 15)
    assert parse_timestamp("06/29/2026 08:15") == datetime(2026, 6, 29, 8, 15)


def test_timestamp_empty():
    for v in (None, "", "N/A", "--"):
        assert parse_timestamp(v) is None
