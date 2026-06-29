"""Tests for opportunities.diff_snapshots (the field-level history diff)."""
from flask_app.opportunities import diff_snapshots


def _snap(**overrides):
    base = {
        'title': 'Trail work', 'body': 'Come help', 'category': 'RM',
        'project_id': '410', 'event_start': '2026-07-01 09:00', 'event_end': None,
        'expiration_date': None, 'location': 'Park', 'city': 'Kyle',
        'anywhere': False, 'anytime': False, 'recurring_weekly': False,
        'recurring_monthly': None, 'recurring_days': None, 'link': None,
        'just_show_up': False,
        # Excluded fields — must never appear in a diff:
        'id': 5, 'owner': 2, 'updated_by': 9,
    }
    base.update(overrides)
    return base


def test_no_changes_returns_empty():
    s = _snap()
    assert diff_snapshots(s, dict(s)) == []


def test_single_field_change():
    changes = diff_snapshots(_snap(title='Old'), _snap(title='New'))
    assert changes == [{'field': 'title', 'label': 'Title', 'old': 'Old', 'new': 'New'}]


def test_multiple_changes_in_field_order():
    before = _snap(title='A', city='Kyle', just_show_up=False)
    after = _snap(title='B', city='Buda', just_show_up=True)
    fields = [c['field'] for c in diff_snapshots(before, after)]
    assert fields == ['title', 'city', 'just_show_up']  # HISTORY_DIFF_FIELDS order


def test_boolean_and_none_values_preserved():
    changes = diff_snapshots(_snap(anytime=False), _snap(anytime=True))
    assert changes == [{'field': 'anytime', 'label': 'Anytime', 'old': False, 'new': True}]


def test_excluded_fields_never_diffed():
    # id/owner/updated_by differ but must not show up.
    changes = diff_snapshots(_snap(id=1, owner=1, updated_by=1),
                             _snap(id=2, owner=2, updated_by=2))
    assert changes == []


def test_missing_previous_treats_all_as_new():
    changes = diff_snapshots(None, _snap(title='X', body='Y'))
    fields = {c['field'] for c in changes}
    # Every non-None field becomes a change; excluded fields still excluded.
    assert 'title' in fields and 'body' in fields
    assert 'id' not in fields and 'owner' not in fields and 'updated_by' not in fields
