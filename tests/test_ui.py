"""Tests for the small formatting helpers in services/ui.py."""
from services.ui import num, pct, tone


def test_pct_formats_with_sign_and_one_decimal():
    assert pct(12.345) == "+12.3%"
    assert pct(-4) == "-4.0%"


def test_pct_none_is_not_available():
    assert pct(None) == "n/a"


def test_pct_can_drop_the_sign():
    assert pct(5, sign=False) == "5.0%"


def test_pct_respects_digit_count():
    assert pct(12.345, digits=0) == "+12%"


def test_num_formats_with_thousands_separator():
    assert num(1234.5) == "1,234.5"


def test_num_none_is_not_available():
    assert num(None) == "n/a"


def test_tone_classifies_direction():
    assert tone(5) == "up"
    assert tone(-5) == "down"
    assert tone(0) == ""


def test_tone_none_is_blank():
    assert tone(None) == ""
