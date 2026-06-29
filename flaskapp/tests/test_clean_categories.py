"""Tests for users.clean_categories.

Parses a spreadsheet "Categories" cell into a deduped, ordered list of valid
category codes, tolerating messy delimiters and recording unknown codes.
"""
from flask_app.users import clean_categories


def test_simple_comma_list():
    assert clean_categories('PO, DO') == ['PO', 'DO']


def test_period_delimiter():
    # The real "PO. DO" typo in the source sheet.
    assert clean_categories('PO. DO') == ['PO', 'DO']


def test_mixed_delimiters_and_case():
    assert clean_categories('po; rm / fr\nCB') == ['PO', 'RM', 'FR', 'CB']


def test_dedupes_preserving_first_order():
    assert clean_categories('PO, PO, DO, po') == ['PO', 'DO']


def test_blank_and_whitespace_tokens_ignored():
    assert clean_categories('PO,,   ,DO') == ['PO', 'DO']


def test_unknown_codes_dropped_and_recorded():
    skipped = set()
    assert clean_categories('PO, ZZ, DO', skipped) == ['PO', 'DO']
    assert skipped == {'ZZ'}


def test_unknown_without_skipped_set_is_silently_dropped():
    assert clean_categories('PO, ZZ') == ['PO']


def test_empty_string():
    assert clean_categories('') == []
