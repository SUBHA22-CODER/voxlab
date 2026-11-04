"""Wispr Flow Dictation Cleaner engine with deliberate failure switch toggles."""

from __future__ import annotations

import re
from failure_config import get as get_failure_config


def process_dictation(raw_text: str, config_override: dict | None = None) -> str:
    """
    Cleans raw speech transcript into polished text:
    - Resolves self-corrections ("Tuesday, no wait, Wednesday" -> "Wednesday")
    - Strips verbal fillers ("um", "uh", "you know")
    - Formats commands ("period" -> ".", "new line" -> "\n")
    - Preserves entities and capitalization
    """
    cfg = dict(get_failure_config())
    if config_override:
        cfg.update(config_override)
    text = raw_text.strip()
    if not text:
        return ""

    # 1. Self-corrections handling
    if not cfg.get("ignore_self_corrections", False):
        # Resolve patterns like: "X, no wait, Y" / "X, scratch that, Y" / "X, actually Y"
        correction_patterns = [
            r"\b[\w\s]+,\s*(?:no\s+wait|wait\s+no|scratch\s+that|actually|i\s+meant)\s*,\s*([\w\s]+)",
            r"\b[\w\s]+\s+(?:no\s+wait|wait\s+no|scratch\s+that|actually)\s+([\w\s]+)",
        ]
        for pat in correction_patterns:
            m = re.search(pat, text, flags=re.IGNORECASE)
            if m:
                # Replace with the corrected suffix
                text = re.sub(pat, r"\1", text, flags=re.IGNORECASE).strip()

    # 2. Filler word cleanup
    if cfg.get("strip_fillers", True):
        # Remove verbal crutches
        fillers = [r"\bum\b", r"\buh\b", r"\byou\s+know\b", r"\bbasically\b"]
        for f in fillers:
            text = re.sub(f, "", text, flags=re.IGNORECASE)
        # Clean double spaces
        text = re.sub(r"\s+", " ", text).strip()

    # 3. Command vs literal handling
    if not cfg.get("literal_period_handling", False):
        # Convert spoken punctuation commands
        text = re.sub(r"(?<!grace\s)\bperiod\b", ".", text, flags=re.IGNORECASE)
        text = re.sub(r"\bcomma\b", ",", text, flags=re.IGNORECASE)
        text = re.sub(r"\bquestion mark\b", "?", text, flags=re.IGNORECASE)
        text = re.sub(r"\bnew line\b", "\n", text, flags=re.IGNORECASE)

    # 4. Name mangling switch (weakness demo)
    if cfg.get("mangle_names", False):
        # Deliberately mangle Indian or technical names
        replacements = {
            r"\bParida\b": "Panda",
            r"\bPriya\b": "Prior",
            r"\bSubha\b": "Super",
            r"\bk8s\b": "kates",
        }
        for pat, sub in replacements.items():
            text = re.sub(pat, sub, text, flags=re.IGNORECASE)

    # 5. Capitalization and sentence formatting
    text = text.strip()
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    if text and not text.endswith((".", "!", "?", "\n")):
        text += "."

    # Clean redundant punctuation spaces
    text = re.sub(r"\s+([.,!?])", r"\1", text)
    return text
