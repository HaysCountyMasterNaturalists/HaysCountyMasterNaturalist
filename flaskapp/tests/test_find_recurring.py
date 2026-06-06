from datetime import datetime, timedelta

import pytest
from pytz import timezone

from flask_app import opportunities as opp_module
from flask_app.opportunities import find_recurring


utc = timezone('UTC')
central = timezone('US/Central')

# Saturday 2026-05-23 12:00 UTC (07:00 CDT). Picked well after DST starts so
# astimezone(central) is unambiguously CDT for all dates in these tests.
FROZEN_NOW = utc.localize(datetime(2026, 5, 23, 12, 0, 0))


@pytest.fixture(autouse=True)
def freeze_now(monkeypatch):
    class FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return FROZEN_NOW.replace(tzinfo=None)
            return FROZEN_NOW.astimezone(tz)

    monkeypatch.setattr(opp_module, 'datetime', FakeDatetime)


def make_opp(**overrides):
    base = {
        'id': 1, 'owner': 1, 'title': 't', 'body': 'b',
        'anywhere': False, 'anytime': False,
        'location': None, 'city': None,
        'event_start': None, 'event_end': None, 'expiration_date': None,
        'category': 'AT', 'project_id': None,
        'recurring_weekly': False, 'recurring_monthly': None,
        'recurring_days': None,
        'link': None, 'just_show_up': False,
    }
    base.update(overrides)
    return base


def _parse_central(s):
    return central.localize(datetime.strptime(s, '%Y-%m-%d %H:%M'))


def test_non_recurring_passes_through_with_local_time_conversion():
    start = utc.localize(datetime(2026, 5, 20, 14, 0, 0))  # 09:00 CDT
    end = utc.localize(datetime(2026, 5, 20, 15, 0, 0))    # 10:00 CDT
    opp = make_opp(event_start=start, event_end=end)

    result = find_recurring([opp])

    assert len(result) == 1
    assert result[0]['event_start'] == '2026-05-20 09:00'
    assert result[0]['event_end'] == '2026-05-20 10:00'


def test_anytime_opp_passes_through():
    result = find_recurring([make_opp(anytime=True)])
    assert len(result) == 1
    assert result[0]['anytime'] is True


def test_weekly_without_recurring_days_uses_event_start_weekday():
    # event_start is well before the 45-day window so expansion starts from
    # fortyfive_days_ago (2026-04-08) — exercises the max() clamp.
    start = utc.localize(datetime(2026, 3, 2, 14, 0, 0))  # Monday
    expiration = utc.localize(datetime(2026, 5, 31, 23, 0, 0))
    opp = make_opp(recurring_weekly=True, event_start=start, expiration_date=expiration)

    result = find_recurring([opp])

    # Mondays in [2026-04-08, 2026-05-31]:
    # 04-13, 04-20, 04-27, 05-04, 05-11, 05-18, 05-25 = 7
    assert len(result) == 7
    for occ in result:
        assert _parse_central(occ['event_start']).weekday() == 0  # Mon


def test_weekly_with_recurring_days_emits_multiple_per_week():
    # recurring_days uses Moment-style indices (0=Sun..6=Sat).
    # "1,3,5" = Mon, Wed, Fri.
    start = utc.localize(datetime(2026, 5, 11, 14, 0, 0))   # Mon
    expiration = utc.localize(datetime(2026, 5, 17, 23, 0, 0))  # following Sun
    opp = make_opp(
        recurring_weekly=True,
        event_start=start,
        expiration_date=expiration,
        recurring_days='1,3,5',
    )

    result = find_recurring([opp])

    # 7-day window contains exactly one Mon, one Wed, one Fri.
    weekdays = sorted(_parse_central(occ['event_start']).weekday() for occ in result)
    assert weekdays == [0, 2, 4]  # Mon, Wed, Fri in Python's weekday()


def test_weekly_respects_expiration_date():
    start = utc.localize(datetime(2026, 5, 4, 14, 0, 0))   # Mon
    expiration = utc.localize(datetime(2026, 5, 12, 23, 0, 0))  # the next Tue
    opp = make_opp(recurring_weekly=True, event_start=start, expiration_date=expiration)

    result = find_recurring([opp])

    # Only 2026-05-04 and 2026-05-11 are Mondays at-or-before the cutoff.
    assert len(result) == 2


def test_weekly_no_expiration_runs_to_six_months_out():
    start = utc.localize(datetime(2026, 5, 4, 14, 0, 0))  # Mon
    opp = make_opp(recurring_weekly=True, event_start=start, expiration_date=None)

    result = find_recurring([opp])

    # Frozen now = 2026-05-23 12:00 UTC; six_months_out = 2026-11-23 12:00 UTC.
    # Loop drops occurrences whose 14:00 UTC stamp exceeds that, so the last
    # Monday included is 2026-11-16. Mondays in [2026-05-04, 2026-11-16] = 29.
    assert len(result) == 29
    for occ in result:
        assert _parse_central(occ['event_start']).weekday() == 0


def test_weekly_recurring_days_overrides_event_start_weekday():
    # event_start is a Monday but recurring_days says Tuesdays only.
    # The Monday should NOT appear in the output.
    start = utc.localize(datetime(2026, 5, 11, 14, 0, 0))  # Mon
    expiration = utc.localize(datetime(2026, 5, 17, 23, 0, 0))
    opp = make_opp(
        recurring_weekly=True,
        event_start=start,
        expiration_date=expiration,
        recurring_days='2',  # Tue only
    )

    result = find_recurring([opp])

    assert len(result) == 1
    assert _parse_central(result[0]['event_start']).weekday() == 1  # Tue


def test_monthly_branch_unchanged_by_weekly_refactor():
    # The PR refactored only the weekly branch; this is a regression check.
    # recurring_monthly = 2 means "2nd week of the month".
    start = utc.localize(datetime(2026, 5, 13, 14, 0, 0))  # 2nd Wed of May
    expiration = utc.localize(datetime(2026, 8, 31, 23, 0, 0))
    opp = make_opp(recurring_monthly=2, event_start=start, expiration_date=expiration)

    result = find_recurring([opp])

    # Expect occurrences for May, June, July, August (4 months in the window).
    assert len(result) >= 3
    for occ in result:
        assert occ['recurring_monthly'] == 2


def test_mixed_list_preserves_non_recurring_alongside_expansions():
    weekly_start = utc.localize(datetime(2026, 5, 4, 14, 0, 0))  # Mon
    weekly_expiration = utc.localize(datetime(2026, 5, 12, 23, 0, 0))
    weekly = make_opp(
        id=1, recurring_weekly=True,
        event_start=weekly_start, expiration_date=weekly_expiration,
    )
    one_off = make_opp(
        id=2,
        event_start=utc.localize(datetime(2026, 5, 20, 14, 0, 0)),
        event_end=utc.localize(datetime(2026, 5, 20, 15, 0, 0)),
    )

    result = find_recurring([weekly, one_off])

    ids = [o['id'] for o in result]
    # 2 Mondays from the weekly expansion + 1 one-off = 3 entries.
    assert len(result) == 3
    assert ids.count(1) == 2
    assert ids.count(2) == 1


class TestCleanRecurringDays:
    """Round-trips of the form-input normalizer used by create/update."""

    def test_repeated_keys(self):
        from werkzeug.datastructures import MultiDict
        form = MultiDict([('recurring_days', '0'), ('recurring_days', '3'), ('recurring_days', '5')])
        assert opp_module.clean_recurring_days(form) == '0,3,5'

    def test_indexed_array_keys(self):
        # Vueform serializes a list HiddenElement as indexed keys:
        # recurring_days[0], recurring_days[1], ...
        from werkzeug.datastructures import MultiDict
        form = MultiDict([('recurring_days[0]', '1'), ('recurring_days[1]', '3'), ('recurring_days[2]', '5')])
        assert opp_module.clean_recurring_days(form) == '1,3,5'

    def test_bracketed_keys(self):
        from werkzeug.datastructures import MultiDict
        form = MultiDict([('recurring_days[]', '1'), ('recurring_days[]', '4')])
        assert opp_module.clean_recurring_days(form) == '1,4'

    def test_single_comma_joined_value(self):
        from werkzeug.datastructures import MultiDict
        form = MultiDict([('recurring_days', '0,2,6')])
        assert opp_module.clean_recurring_days(form) == '0,2,6'

    def test_empty_returns_none(self):
        from werkzeug.datastructures import MultiDict
        assert opp_module.clean_recurring_days(MultiDict()) is None

    def test_strips_empty_entries(self):
        from werkzeug.datastructures import MultiDict
        form = MultiDict([('recurring_days', '0,,3, ,5')])
        assert opp_module.clean_recurring_days(form) == '0,3,5'
