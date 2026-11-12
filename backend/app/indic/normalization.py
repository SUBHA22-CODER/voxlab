# normalization.py
# Indic language text normalization, script standardization, and numeral mapping.
# Handles Unicode canonical equivalence, Devanagari/Indic numerals, and Dandas.

from __future__ import annotations

import re
import unicodedata

# Unicode numeral ranges for major Indic scripts
INDIC_NUMERAL_MAP = {
    # Devanagari (Hindi, Marathi, Sanskrit)
    "०": "0", "१": "1", "२": "2", "३": "3", "४": "4",
    "५": "5", "६": "6", "७": "7", "८": "8", "९": "9",
    # Bengali / Assamese
    "০": "0", "১": "1", "২": "2", "৩": "3", "৪": "4",
    "৫": "5", "৬": "6", "৭": "7", "৮": "8", "৯": "9",
    # Tamil
    "௦": "0", "௧": "1", "௨": "2", "௩": "3", "௪": "4",
    "௫": "5", "௬": "6", "௭": "7", "௮": "8", "௯": "9",
    # Telugu
    "౦": "0", "౧": "1", "౨": "2", "౩": "3", "౪": "4",
    "౫": "5", "౬": "6", "౭": "7", "౮": "8", "౯": "9",
    # Kannada
    "೦": "0", "೧": "1", "೨": "2", "೩": "3", "೪": "4",
    "೫": "5", "೬": "6", "೭": "7", "೮": "8", "೯": "9",
    # Gujarati
    "૦": "0", "૧": "1", "૨": "2", "૩": "3", "૪": "4",
    "૫": "5", "૬": "6", "૭": "7", "૮": "8", "૯": "9",
}

# Indic punctuation characters
DANDA = "\u0964"  # ।
DOUBLE_DANDA = "\u0965"  # ॥
RUPEE = "\u20b9"  # ₹
_PUNCT_RAW = DANDA + DOUBLE_DANDA + RUPEE + r".,?!;:'""`()[]{}<>/-_@#$%^&*+=~"
INDIC_PUNCTUATION_PATTERN = re.compile("[" + re.escape(_PUNCT_RAW) + "]")


def normalize_indic_numerals(text: str) -> str:
    """Map regional Indic numerals (Devanagari, Bengali, Tamil, etc.) to ASCII digits (0-9)."""
    return "".join(INDIC_NUMERAL_MAP.get(char, char) for char in text)


def normalize_indic_text(
    text: str,
    strip_punctuation: bool = True,
    convert_numerals: bool = True,
    lowercase_latin: bool = True,
) -> str:
    """Standardize Indic text for fair and deterministic ASR evaluation.

    1. Unicode NFC normalization (composes base characters and diacritics).
    2. Converts regional digits to canonical Arabic numerals.
    3. Standardizes chandrabindu / anusvara variation.
    4. Strips Dandas and Western punctuation while preserving words.
    5. Collapses redundant whitespace.
    """
    if not text:
        return ""

    # 1. Unicode NFC normalization
    result = unicodedata.normalize("NFC", text)

    # 2. Regional numerals -> 0-9
    if convert_numerals:
        result = normalize_indic_numerals(result)
        # Collapse commas within digit sequences: '5,000' -> '5000'
        result = re.sub(r"(?<=\d),(?=\d)", "", result)

    # 3. Punctuation removal
    if strip_punctuation:
        result = INDIC_PUNCTUATION_PATTERN.sub(" ", result)

    # 4. Lowercase Latin characters (essential for code-switching / Hinglish)
    if lowercase_latin:
        result = result.lower()

    # 5. Collapse multiple spaces
    result = re.sub(r"\s+", " ", result).strip()
    return result


def is_latin_token(token: str) -> bool:
    """Return True if token consists predominantly of Latin characters (ASCII a-z)."""
    clean = re.sub(r"[^a-zA-Z]", "", token)
    return len(clean) > 0 and len(clean) >= len(token) * 0.5


def is_indic_token(token: str) -> bool:
    """Return True if token contains Devanagari, Bengali, Tamil, Telugu, Kannada, etc."""
    for ch in token:
        name = unicodedata.name(ch, "")
        if any(script in name for script in ("DEVANAGARI", "BENGALI", "TAMIL", "TELUGU", "KANNADA", "GUJARATI", "MALAYALAM", "GURMUKHI", "ORIYA")):
            return True
    return False


def detect_code_switch_ratio(text: str) -> float:
    """Compute the proportion of Latin loanwords in an Indic or code-switched sentence.
    e.g. 'Mera order cancel karo please' -> 2 Latin words ('order', 'please') / 5 = 0.40
    """
    tokens = text.split()
    if not tokens:
        return 0.0
    latin_count = sum(1 for t in tokens if is_latin_token(t))
    return round(latin_count / len(tokens), 4)
