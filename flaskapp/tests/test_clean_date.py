"""Tests for opportunities.clean_date.

Covers the date/datetime formats the form submits -- 24-hour 'YYYY-MM-DD HH:MM'
(event_start/event_end) and date-only 'YYYY-MM-DD' (expiration_date) -- plus a
legacy ' am'/' pm' suffix, all interpreted as Central and returned as UTC.
"""
from datetime import datetime

import pytest
from pytz import timezone

from flask_app.opportunities import clean_date

utc = timezone('UTC')

# 2026-01-31 is CST (UTC-6); 2026-07-15 is CDT (UTC-5) -- covers both offsets.


@pytest.mark.parametrize('value, expected', [
    # 24-hour datetime (event_start / event_end).
    ('2026-01-31 11:30', datetime(2026, 1, 31, 17, 30)),
    ('2026-01-31 23:05', datetime(2026, 2, 1, 5, 5)),
    ('2026-01-31 00:00', datetime(2026, 1, 31, 6, 0)),
    # Daylight time -> UTC-5.
    ('2026-07-15 11:30', datetime(2026, 7, 15, 16, 30)),
    # Date-only (expiration_date) -> midnight Central.
    ('2026-01-31', datetime(2026, 1, 31, 6, 0)),
    # Legacy am/pm suffix still tolerated.
    ('2026-01-31 11:30 am', datetime(2026, 1, 31, 17, 30)),
    ('2026-01-31 01:30 pm', datetime(2026, 1, 31, 19, 30)),
    ('2026-01-31 12:00 pm', datetime(2026, 1, 31, 18, 0)),  # noon: no +12
])
def test_clean_date_parses_central_to_utc(value, expected):
    assert clean_date(value) == utc.localize(expected)


def test_clean_date_returns_aware_utc():
    result = clean_date('2026-01-31 11:30')
    assert result.tzinfo is not None
    assert result.utcoffset().total_seconds() == 0


@pytest.mark.parametrize('empty', [None, '', '   '])
def test_clean_date_empty_is_none(empty):
    assert clean_date(empty) is None


def test_clean_date_rejects_unparseable():
    with pytest.raises(ValueError):
        clean_date('not-a-date')
