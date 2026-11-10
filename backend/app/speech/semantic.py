# semantic.py
# Semantic error intelligence (VoxLab 2.5 Phase 3) — the DETERMINISTIC layer.
#
# Detects meaning-changing differences between a reference transcript and the
# recognized transcript using word alignment + rule-based detectors. This
# layer is deterministic and reproducible: same inputs, same errors, always.
#
# The LLM-based judgment lives in semantic_llm.py and is a SEPARATE layer:
# every LLM verdict is labeled with its model, prompt version, timestamp,
# input/output, and confidence — and is never treated as ground truth.

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .metrics import STOP_WORDS
from .alignment import (
    OP_DELETION,
    OP_SUBSTITUTION,
    SEV_MAJOR,
    AlignmentResult,
    align_words,
)
from .metrics import extract_numbers

# --- deterministic detector primitives ----------------------------------------

MONTHS = {
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
}
WEEKDAYS = {
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
}
NEGATION_TOKENS = {"not", "no", "never", "dont", "doesnt", "didnt", "wont", "cannot", "cant", "isnt", "wasnt", "arent", "werent"}
IMPERATIVE_HINTS = {"schedule", "deploy", "send", "cancel", "create", "update", "delete", "run", "start", "stop", "call", "email", "ship", "fix", "write", "review", "set", "order"}
# Morphological variants that do NOT change meaning when substituted.
MORPH_VARIANTS = {
    "run": "running", "deploy": "deployed", "ship": "shipped", "order": "ordered",
    "start": "started", "stop": "stopped", "call": "called", "email": "emailed",
}


@dataclass
class SemanticError:
    error_type: str
    severity: str  # "critical" | "major" | "minor"
    description: str
    reference_text: str | None
    hypothesis_text: str | None
    ref_index: int | None = None
    hyp_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.error_type,
            "severity": self.severity,
            "description": self.description,
            "reference": self.reference_text,
            "hypothesis": self.hypothesis_text,
            "ref_index": self.ref_index,
            "hyp_index": self.hyp_index,
        }


@dataclass
class SemanticAnalysis:
    errors: list[SemanticError] = field(default_factory=list)
    meaning_preserved: bool = True
    alignment: AlignmentResult | None = None

    @property
    def error_count(self) -> int:
        return len(self.errors)

    def to_dict(self) -> dict[str, Any]:
        return {
            "meaning_preserved": self.meaning_preserved,
            "error_count": self.error_count,
            "errors": [e.to_dict() for e in self.errors],
        }


def _norm(word: str) -> str:
    return word.lower().strip('.,!?;:"\'()[]{}')


def _extract_dates(text: str) -> list[str]:
    """Normalized date mentions: month names, weekdays, numeric dates."""
    tokens = [_norm(t) for t in text.split()]
    dates = [t for t in tokens if t in MONTHS or t in WEEKDAYS]
    dates += [m.group(0) for m in re.finditer(r"\b\d{1,2}[/.-]\d{1,2}([/.-]\d{2,4})?\b", text)]
    return dates


def _numbers_in_text(text: str) -> list[float]:
    """Numeric values including number-words mapped to values (small set)."""
    values = list(extract_numbers(text))
    word_values = {
        "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
        "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
        "thousand": 1000,
    }
    for token in text.lower().split():
        cleaned = _norm(token)
        if cleaned in word_values:
            values.append(float(word_values[cleaned]))
    return values


def analyze_semantic_errors(
    reference: str,
    hypothesis: str,
    *,
    entities: list[str] | None = None,
    technical_vocab: list[str] | None = None,
) -> SemanticAnalysis:
    """Full deterministic semantic analysis. Deterministic: no randomness,
    no model calls; identical inputs always produce identical output."""
    alignment = align_words(reference, hypothesis)
    analysis = SemanticAnalysis(alignment=alignment)

    ref_tokens = [_norm(t) for t in reference.split()]
    hyp_tokens_set = {_norm(t) for t in hypothesis.split()}

    # 1. Meaning-changing substitutions (content-word substitutions that are
    #    not morphological variants of each other).
    for token in alignment.tokens:
        if token.operation != OP_SUBSTITUTION:
            continue
        ref_n, hyp_n = _norm(token.ref_word or ""), _norm(token.hyp_word or "")
        if not ref_n or not hyp_n:
            continue
        if not _is_meaning_changing(ref_n, hyp_n):
            continue
        error_type = "substitution"
        for detector, label in (
            (_is_number_confusion, "number_error"),
            (_is_negation_confusion, "negation_error"),
        ):
            if detector(ref_n, hyp_n):
                error_type = label
                break
        analysis.errors.append(
            SemanticError(
                error_type=error_type,
                severity="critical" if error_type in ("number_error", "negation_error") else SEV_MAJOR,
                description=token.explanation or "",
                reference_text=token.ref_word,
                hypothesis_text=token.hyp_word,
                ref_index=token.ref_index,
                hyp_index=token.hyp_index,
            )
        )

    # 2. Missing content words (deletions) — potential missing instructions.
    for token in alignment.tokens:
        if token.operation != OP_DELETION or _norm(token.ref_word or "") in STOP_WORDS:
            continue
        ref_n = _norm(token.ref_word or "")
        error_type = "missing_word"
        if ref_n in IMPERATIVE_HINTS:
            error_type = "missing_instruction"
        elif ref_n in MONTHS or ref_n in WEEKDAYS:
            error_type = "date_error"
        analysis.errors.append(
            SemanticError(
                error_type=error_type,
                severity="critical" if error_type == "missing_instruction" else SEV_MAJOR,
                description=token.explanation or "",
                reference_text=token.ref_word,
                hypothesis_text=None,
                ref_index=token.ref_index,
            )
        )

    # 3. Number set mismatch (catches rewrites the word alignment missed).
    #    Skipped when the alignment already reported a number_error so one
    #    real mistake is not double-counted.
    ref_numbers = _numbers_in_text(reference)
    hyp_numbers = _numbers_in_text(hypothesis)
    if (
        ref_numbers
        and not _multiset_contains(ref_numbers, hyp_numbers)
        and not any(e.error_type == "number_error" for e in analysis.errors)
    ):
        missing = _multiset_difference(ref_numbers, hyp_numbers)
        if missing:
            analysis.errors.append(
                SemanticError(
                    error_type="number_error",
                    severity="critical",
                    description=f"reference numbers {missing} not correctly recognized",
                    reference_text=str(ref_numbers),
                    hypothesis_text=str(hyp_numbers),
                )
            )

    # 4. Date mentions present in one side only.
    ref_dates = _extract_dates(reference)
    hyp_dates = _extract_dates(hypothesis)
    if ref_dates and sorted(ref_dates) != sorted(hyp_dates):
        analysis.errors.append(
            SemanticError(
                error_type="date_error",
                severity="critical",
                description=f"date mentions differ: reference {ref_dates} vs transcript {hyp_dates}",
                reference_text=", ".join(ref_dates),
                hypothesis_text=", ".join(hyp_dates),
            )
        )

    # 5. Negation presence mismatch (whole-utterance level).
    ref_neg = {t for t in ref_tokens if t in NEGATION_TOKENS}
    hyp_neg = {t for t in hyp_tokens_set if t in NEGATION_TOKENS}
    if ref_neg != hyp_neg:
        analysis.errors.append(
            SemanticError(
                error_type="negation_error",
                severity="critical",
                description=f"negation words differ: reference {sorted(ref_neg)} vs transcript {sorted(hyp_neg)}",
                reference_text=" ".join(sorted(ref_neg)),
                hypothesis_text=" ".join(sorted(hyp_neg)),
            )
        )

    # 6. Entity substitutions (provided list).
    for entity in entities or []:
        if entity.strip() and _norm(entity) not in hyp_tokens_set:
            analysis.errors.append(
                SemanticError(
                    error_type="entity_error",
                    severity=SEV_MAJOR,
                    description=f"entity {entity!r} missing or altered in transcript",
                    reference_text=entity,
                    hypothesis_text=None,
                )
            )

    # 7. Technical terminology errors (provided list).
    for term in technical_vocab or []:
        if term.strip() and _norm(term) not in hyp_tokens_set:
            analysis.errors.append(
                SemanticError(
                    error_type="terminology_error",
                    severity=SEV_MAJOR,
                    description=f"technical term {term!r} missing or altered in transcript",
                    reference_text=term,
                    hypothesis_text=None,
                )
            )

    # 8. Intent change: question vs statement (token ORDER matters here, so
    #    both sides use their ordered token lists, not sets).
    question_starters = (
        "what", "when", "where", "who", "why", "how", "is", "are", "can", "could", "does", "did",
    )
    ref_question = reference.strip().endswith("?") or any(
        t in question_starters for t in ref_tokens[:2]
    )
    hyp_question = hypothesis.strip().endswith("?") or any(
        t in question_starters for t in [_norm(t) for t in hypothesis.split()][:2]
    )
    if ref_question != hyp_question:
        analysis.errors.append(
            SemanticError(
                error_type="intent_change",
                severity=SEV_MAJOR,
                description="utterance intent changed (question vs statement)",
                reference_text="question" if ref_question else "statement",
                hypothesis_text="question" if hyp_question else "statement",
            )
        )

    # Meaning is "preserved" only when no critical/major error exists.
    analysis.meaning_preserved = not any(e.severity in ("critical", SEV_MAJOR) for e in analysis.errors)
    return analysis


def _is_meaning_changing(ref_norm: str, hyp_norm: str) -> bool:
    """Substitutions that are mere morphology or trivial spelling variants
    do not change meaning."""
    if ref_norm == hyp_norm:
        return False
    variant = MORPH_VARIANTS.get(ref_norm)
    if variant and (hyp_norm == variant or hyp_norm == ref_norm + "s"):
        return False
    if ref_norm.rstrip("s") == hyp_norm.rstrip("s"):
        return False  # plural/singular
    return True


def _is_number_confusion(ref_norm: str, hyp_norm: str) -> bool:
    number_words = {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
                    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
                    "eighteen", "nineteen", "twenty", "thirty", "forty", "fifty", "sixty",
                    "seventy", "eighty", "ninety", "hundred", "thousand"}
    return ref_norm in number_words and hyp_norm in number_words


def _is_negation_confusion(ref_norm: str, hyp_norm: str) -> bool:
    return (ref_norm in NEGATION_TOKENS) != (hyp_norm in NEGATION_TOKENS)


def _multiset_contains(needles: list[float], haystack: list[float]) -> bool:
    pool = list(haystack)
    for n in needles:
        if n in pool:
            pool.remove(n)
        else:
            return False
    return True


def _multiset_difference(needles: list[float], haystack: list[float]) -> list[float]:
    pool = list(haystack)
    missing: list[float] = []
    for n in needles:
        if n in pool:
            pool.remove(n)
        else:
            missing.append(n)
    return missing
