"""Tests for opportunities.convert_to_readable_local.

DB datetimes are stored as naive UTC; this formats them as Central
'YYYY-MM-DD HH:MM' for display (used by /api/users last_login and history).
"""
from datetime import datetime

from flask_app.opportunities import convert_to_readable_local


def test_standard_time_utc_minus_6():
    # 2026-01-31 is CST (UTC-6).
    assert convert_to_readable_local(datetime(2026, 1, 31, 17, 30)) == '2026-01-31 11:30'


def test_daylight_time_utc_minus_5():
    # 2026-07-15 is CDT (UTC-5).
    assert convert_to_readable_local(datetime(2026, 7, 15, 16, 30)) == '2026-07-15 11:30'


def test_crosses_local_midnight_backwards():
    # 02:30 UTC on Jul 15 is 21:30 the previous day in Central.
    assert convert_to_readable_local(datetime(2026, 7, 15, 2, 30)) == '2026-07-14 21:30'


def test_none_returns_none():
    assert convert_to_readable_local(None) is None
