# test_indic_normalization.py
# Unit tests for Indic language text normalization, numeral conversion, and code-switching metrics.

from __future__ import annotations

import pytest

from app.indic.normalization import (
    detect_code_switch_ratio,
    is_indic_token,
    is_latin_token,
    normalize_indic_numerals,
    normalize_indic_text,
)


def test_devanagari_numerals_conversion() -> None:
    # ०१२३४५६७८९ -> 0123456789
    text = "खाते में ₹५,४२० रुपये हैं"
    converted = normalize_indic_numerals(text)
    assert "5,420" in converted


def test_bengali_and_tamil_numerals() -> None:
    # Bengali: ১২৩৪ -> 1234
    assert normalize_indic_numerals("১২৩৪") == "1234"
    # Tamil: ௧௨௩௪ -> 1234
    assert normalize_indic_numerals("௧௨௩௪") == "1234"
    # Telugu: ౧౨౩౪ -> 1234
    assert normalize_indic_numerals("౧౨౩౪") == "1234"


def test_indic_punctuation_and_danda_stripping() -> None:
    # Strips Devanagari Danda (।) and double Danda (॥)
    raw = "यह परीक्षण वाक्य है। कृपया इसकी जांच करें॥"
    norm = normalize_indic_text(raw)
    assert "।" not in norm
    assert "॥" not in norm
    assert norm == "यह परीक्षण वाक्य है कृपया इसकी जांच करें"


def test_code_switch_detection() -> None:
    # "मेरा refund अभी तक initiate नहीं हुआ" -> 2 English words ('refund', 'initiate') out of 7 = ~0.2857
    hinglish = "मेरा refund अभी तक initiate नहीं हुआ"
    ratio = detect_code_switch_ratio(hinglish)
    assert pytest.approx(ratio, 0.05) == 0.2857

    # Pure English
    assert detect_code_switch_ratio("Please check my order status") == 1.0

    # Pure Devanagari Hindi
    assert detect_code_switch_ratio("कृपया मेरा बैलेंस बताएं") == 0.0


def test_is_latin_and_indic_token() -> None:
    assert is_latin_token("refund") is True
    assert is_latin_token("बैलेंस") is False
    assert is_indic_token("बैलेंस") is True
    assert is_indic_token("refund") is False
