"""Tests for the opportunity edit-permission rule (#26).

Edit rights are permission-based, not ownership-based, and keyed on the exact
(project, category) combination:
- admins may edit anything;
- AT/EV are exempt and editable by any coordinator;
- every other opportunity requires the user to be assigned to its specific
  (project_id, category) combo. Being the owner/creator grants nothing.
"""
from flask_app.opportunities import _edit_allowed, combo_key


def test_admin_may_edit_anything():
    assert _edit_allowed(True, False, 'RM', '410', []) is True


def test_coordinator_assigned_to_combo_may_edit():
    assert _edit_allowed(False, True, 'RM', '410', [combo_key('410', 'RM')]) is True


def test_assignment_is_category_specific():
    # Assigned to 410/NPA must NOT grant editing 410/RM.
    assert _edit_allowed(False, True, 'RM', '410', [combo_key('410', 'NPA')]) is False


def test_coordinator_not_assigned_may_not_edit():
    # "owner is not a grant": unassigned coordinator can't edit.
    assert _edit_allowed(False, True, 'RM', '999', [combo_key('410', 'RM')]) is False


def test_exempt_categories_editable_by_any_coordinator():
    assert _edit_allowed(False, True, 'AT', None, []) is True
    assert _edit_allowed(False, True, 'EV', None, []) is True


def test_exempt_category_still_requires_coordinator():
    assert _edit_allowed(False, False, 'AT', None, []) is False


def test_non_coordinator_non_admin_denied():
    # A revoked coordinator with a leftover assignment still cannot edit.
    assert _edit_allowed(False, False, 'RM', '410', [combo_key('410', 'RM')]) is False


def test_handles_missing_assignments_list():
    assert _edit_allowed(False, True, 'RM', '410', None) is False
