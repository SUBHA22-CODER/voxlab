# alignment.py
# Word-level error localization (VoxLab 2.5 Phase 4): aligns a reference
# transcript with the recognized transcript and labels every token as
# correct, substitution, insertion, or deletion.
#
# Honesty rules:
# - Timestamps and confidences are attached ONLY when the engine provided
#   them (word_timestamps output). Nothing is ever interpolated or invented.
# - Severity distinguishes content words (domain-bearing) from function
#   words; a substitution of a content word is "major", a punctuation-level
#   or function-word difference is "minor".

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .metrics import STOP_WORDS

# Operations
OP_CORRECT = "correct"
OP_SUBSTITUTION = "substitution"
OP_INSERTION = "insertion"
OP_DELETION = "deletion"

# Severities
SEV_MAJOR = "major"
SEV_MINOR = "minor"


@dataclass
class WordTiming:
    start_seconds: float
    end_seconds: float
    confidence: float | None = None  # engine-provided only


@dataclass
class AlignedToken:
    operation: str
    ref_index: int | None
    hyp_index: int | None
    ref_word: str | None
    hyp_word: str | None
    severity: str | None = None  # None for correct words
    # Engine word timings when available (start/end of the HYPOTHESIS word for
    # correct/substitution/insertion; the reference has no timing of its own).
    timing: WordTiming | None = None
    explanation: str | None = None


@dataclass
class AlignmentResult:
    tokens: list[AlignedToken] = field(default_factory=list)
    ref_word_count: int = 0
    hyp_word_count: int = 0
    correct: int = 0
    substitutions: int = 0
    insertions: int = 0
    deletions: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tokens": [
                {
                    "operation": t.operation,
                    "ref_index": t.ref_index,
                    "hyp_index": t.hyp_index,
                    "ref_word": t.ref_word,
                    "hyp_word": t.hyp_word,
                    "severity": t.severity,
                    "start_seconds": t.timing.start_seconds if t.timing else None,
                    "end_seconds": t.timing.end_seconds if t.timing else None,
                    "confidence": t.timing.confidence if t.timing else None,
                    "explanation": t.explanation,
                }
                for t in self.tokens
            ],
            "counts": {
                "reference_words": self.ref_word_count,
                "hypothesis_words": self.hyp_word_count,
                "correct": self.correct,
                "substitutions": self.substitutions,
                "insertions": self.insertions,
                "deletions": self.deletions,
            },
        }


def _norm(word: str) -> str:
    return word.lower().strip('.,!?;:"\'()[]{}')


def _is_content_word(word: str) -> bool:
    return bool(word) and _norm(word) not in STOP_WORDS


def _match_cost(ref_word: str, hyp_word: str) -> bool:
    """Loose equality: case- and punctuation-insensitive."""
    return _norm(ref_word) == _norm(hyp_word)


def align_words(
    reference: str,
    hypothesis: str,
    word_timings: list[WordTiming] | None = None,
) -> AlignmentResult:
    """Needleman-Wunsch style alignment (Levenshtein backtrace) at word
    level. `word_timings` must be hypothesis-aligned (one entry per
    hypothesis token) when the engine provides word timestamps; it is used
    only for display, never to drive the alignment."""
    ref = reference.split()
    hyp = hypothesis.split()
    result = AlignmentResult(ref_word_count=len(ref), hyp_word_count=len(hyp))
    if not ref and not hyp:
        return result

    rows, cols = len(ref) + 1, len(hyp) + 1
    # Cost matrix: substitutions cost 1 (0 on loose match); ins/del cost 1.
    matrix = [[0] * cols for _ in range(rows)]
    for i in range(1, rows):
        matrix[i][0] = i
    for j in range(1, cols):
        matrix[0][j] = j
    for i in range(1, rows):
        for j in range(1, cols):
            cost = 0 if _match_cost(ref[i - 1], hyp[j - 1]) else 1
            matrix[i][j] = min(
                matrix[i - 1][j] + 1,
                matrix[i][j - 1] + 1,
                matrix[i - 1][j - 1] + cost,
            )

    i, j = len(ref), len(hyp)
    back: list[AlignedToken] = []
    while i > 0 or j > 0:
        timing = word_timings[j - 1] if (word_timings and 0 < j <= len(word_timings)) else None
        if i > 0 and j > 0 and _match_cost(ref[i - 1], hyp[j - 1]) and matrix[i][j] == matrix[i - 1][j - 1]:
            back.append(AlignedToken(OP_CORRECT, i - 1, j - 1, ref[i - 1], hyp[j - 1], timing=timing))
            result.correct += 1
            i, j = i - 1, j - 1
        elif i > 0 and j > 0 and matrix[i][j] == matrix[i - 1][j - 1] + 1:
            severity = SEV_MAJOR if _is_content_word(ref[i - 1]) else SEV_MINOR
            back.append(
                AlignedToken(
                    OP_SUBSTITUTION,
                    i - 1,
                    j - 1,
                    ref[i - 1],
                    hyp[j - 1],
                    severity,
                    timing=timing,
                    explanation=f"reference word {ref[i - 1]!r} recognized as {hyp[j - 1]!r}",
                )
            )
            result.substitutions += 1
            i, j = i - 1, j - 1
        elif i > 0 and matrix[i][j] == matrix[i - 1][j] + 1:
            back.append(
                AlignedToken(
                    OP_DELETION,
                    i - 1,
                    None,
                    ref[i - 1],
                    None,
                    SEV_MAJOR if _is_content_word(ref[i - 1]) else SEV_MINOR,
                    explanation=f"reference word {ref[i - 1]!r} missing from transcript",
                )
            )
            result.deletions += 1
            i -= 1
        else:
            back.append(
                AlignedToken(
                    OP_INSERTION,
                    None,
                    j - 1,
                    None,
                    hyp[j - 1],
                    SEV_MAJOR if _is_content_word(hyp[j - 1]) else SEV_MINOR,
                    timing=timing,
                    explanation=f"extra word {hyp[j - 1]!r} not present in reference",
                )
            )
            result.insertions += 1
            j -= 1

    result.tokens = list(reversed(back))
    return result
