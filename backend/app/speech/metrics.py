# metrics.py
# Transcription accuracy metrics for VoxLab 2.0 — the ground-truth layer of the
# evaluation engine.
#
# Definitions (documented per the product rule: never combine metrics without
# recording their definitions and normalization):
#
#   WER = (substitutions + deletions + insertions) / reference_word_count
#         (can exceed 1.0 when the hypothesis inserts many extra words)
#   CER = character_edit_distance / reference_character_count
#   RTF = processing_time_seconds / audio_duration_seconds   (real-time factor)
#
# Normalization is CONFIGURABLE, never silent: "twenty five" vs "25" is only
# counted equal when normalization.expand_numbers is enabled, and every metric
# result records which normalization rules were applied.
#
# Honesty rules:
# - Metrics here are deterministic text comparisons (ground truth layer).
# - Heuristic signals (semantic word-overlap proxy) are returned separately
#   and are NOT to be presented as ground truth. Any future LLM-based semantic
#   judge must be labeled separately with its model + configuration.

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

# --- normalization --------------------------------------------------------------

# Filler tokens removed when NormalizationConfig.remove_fillers is enabled.
FILLER_TOKENS = frozenset({"um", "uh", "erm", "uhh", "umm", "hmm"})

CONTRACTIONS: dict[str, str] = {
    "i'm": "i am",
    "you're": "you are",
    "he's": "he is",
    "she's": "she is",
    "it's": "it is",
    "we're": "we are",
    "they're": "they are",
    "can't": "cannot",
    "won't": "will not",
    "don't": "do not",
    "doesn't": "does not",
    "didn't": "did not",
    "isn't": "is not",
    "aren't": "are not",
    "wasn't": "was not",
    "weren't": "were not",
    "haven't": "have not",
    "hasn't": "has not",
    "i've": "i have",
    "we've": "we have",
    "i'll": "i will",
    "we'll": "we will",
    "let's": "let us",
    "that's": "that is",
    "there's": "there is",
    "what's": "what is",
}

PUNCT_PATTERN = re.compile(r"[^\w\s]", re.UNICODE)
NUMBER_TOKEN_PATTERN = re.compile(
    r"\d+(?:\.\d+)?|[a-z]+(?:[-\s][a-z]+)*", re.IGNORECASE
)


@dataclass
class NormalizationConfig:
    """Which normalization rules apply before metric comparison."""

    lowercase: bool = True
    strip_punctuation: bool = True
    expand_contractions: bool = True
    expand_numbers: bool = False
    remove_fillers: bool = False
    unicode_fold: bool = True

    def signature(self) -> dict[str, bool]:
        return {
            "lowercase": self.lowercase,
            "strip_punctuation": self.strip_punctuation,
            "expand_contractions": self.expand_contractions,
            "expand_numbers": self.expand_numbers,
            "remove_fillers": self.remove_fillers,
            "unicode_fold": self.unicode_fold,
        }


def _expand_contractions(text: str) -> str:
    def _sub(match: re.Match[str]) -> str:
        return CONTRACTIONS.get(match.group(0).lower(), match.group(0))

    return re.sub(r"\b[\w']+\b", _sub, text)


def number_to_words(number: float) -> str:
    """English words for a number ("25" -> "twenty five").

    Supports integers up to 999,999,999 and one decimal place ("2.5" ->
    "two point five"). Deterministic and dependency-free.
    """
    if math.isnan(number) or number in (float("inf"), float("-inf")):  # NaN/inf
        raise ValueError("cannot spell non-finite number")

    negative = number < 0
    value = abs(number)
    integer_part = int(value)
    fraction = value - integer_part

    words = ("minus " if negative else "") + _int_to_words(integer_part)
    if fraction > 1e-9:
        decimal_digits = f"{fraction:.6f}".rstrip("0").split(".")[1]
        words += " point " + " ".join(_DIGITS_SINGLE[int(d)] for d in decimal_digits)
    return words


_ONES = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen",
]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
         "eighty", "ninety"]
_DIGITS_SINGLE = ["zero", "one", "two", "three", "four", "five", "six",
                  "seven", "eight", "nine"]


def _int_to_words(n: int) -> str:
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens = _TENS[n // 10]
        rest = n % 10
        return tens if rest == 0 else f"{tens} {_ONES[rest]}"
    if n < 1000:
        hundreds = f"{_ONES[n // 100]} hundred"
        rest = n % 100
        return hundreds if rest == 0 else f"{hundreds} {_int_to_words(rest)}"
    for divisor, label in ((1_000_000, "million"), (1_000, "thousand")):
        if n >= divisor:
            head = _int_to_words(n // divisor)
            tail = n % divisor
            return head + f" {label}" + (f" {_int_to_words(tail)}" if tail else "")
    return str(n)


_NUM_IN_TEXT = re.compile(r"\b\d+(?:\.\d+)?\b")


def _expand_numbers(text: str) -> str:
    def _sub(match: re.Match[str]) -> str:
        token = match.group(0)
        try:
            return number_to_words(float(token))
        except ValueError:
            return token

    return _NUM_IN_TEXT.sub(_sub, text)


def normalize_text(text: str, config: NormalizationConfig) -> str:
    """Apply the configured normalization chain. Order matters and is fixed:
    unicode fold -> lowercase -> contractions -> numbers -> fillers ->
    punctuation strip -> whitespace collapse."""
    out = text
    if config.unicode_fold:
        out = unicodedata.normalize("NFKD", out)
        out = "".join(ch for ch in out if not unicodedata.combining(ch))
    if config.lowercase:
        out = out.lower()
    if config.expand_contractions:
        out = _expand_contractions(out)
    if config.expand_numbers:
        out = _expand_numbers(out)
    if config.remove_fillers:
        tokens = [
            t for t in out.split()
            if t.strip(".,!?;:") not in ("um", "uh", "erm", "hmm")
        ]
        out = " ".join(tokens)
    if config.strip_punctuation:
        out = PUNCT_PATTERN.sub(" ", out)
    return re.sub(r"\s+", " ", out).strip()


# --- edit distances ----------------------------------------------------------------


def _edit_distance_matrix(a: Sequence[str], b: Sequence[str]) -> list[list[int]]:
    rows, cols = len(a) + 1, len(b) + 1
    matrix = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        matrix[i][0] = i
    for j in range(cols):
        matrix[0][j] = j
    for i in range(1, rows):
        for j in range(1, cols):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            matrix[i][j] = min(
                matrix[i - 1][j] + 1,      # deletion
                matrix[i][j - 1] + 1,      # insertion
                matrix[i - 1][j - 1] + cost,  # substitution
            )
    return matrix


def word_error_rate(
    reference: str, hypothesis: str
) -> tuple[float, dict[str, int]]:
    """WER with full S/D/I backtrace. Reference word count 0 -> 0.0 if both
    empty else 1.0 (any hypothesis on an empty reference is total error)."""
    ref = reference.split()
    hyp = hypothesis.split()
    if not ref:
        return (0.0 if not hyp else 1.0), {
            "substitutions": 0, "deletions": 0, "insertions": len(hyp),
            "reference_words": 0,
        }
    matrix = _edit_distance_matrix(ref, hyp)
    i, j = len(ref), len(hyp)
    subs = dels = ins = 0
    while i > 0 or j > 0:
        if i > 0 and j > 0 and matrix[i][j] == matrix[i - 1][j - 1] and ref[i - 1] == hyp[j - 1]:
            i, j = i - 1, j - 1
        elif i > 0 and j > 0 and matrix[i][j] == matrix[i - 1][j - 1] + 1:
            subs += 1
            i, j = i - 1, j - 1
        elif i > 0 and matrix[i][j] == matrix[i - 1][j] + 1:
            dels += 1
            i -= 1
        else:
            ins += 1
            j -= 1
    wer = (subs + dels + ins) / len(ref)
    return wer, {
        "substitutions": subs,
        "deletions": dels,
        "insertions": ins,
        "reference_words": len(ref),
    }


def char_error_rate(reference: str, hypothesis: str) -> float:
    """CER over characters (spaces included, matching standard practice)."""
    if not reference:
        return 0.0 if not hypothesis else 1.0
    dist = _edit_distance_matrix(list(reference), list(hypothesis))[-1][-1]
    return dist / len(reference)


# --- component accuracies ------------------------------------------------------------


def punctuation_sequence(text: str) -> list[str]:
    return PUNCT_PATTERN.findall(text)


def punctuation_accuracy(reference: str, hypothesis: str) -> float | None:
    """1 - normalized edit distance over the punctuation mark sequences.
    None when the reference contains no punctuation (nothing to score)."""
    ref_p = punctuation_sequence(reference)
    if not ref_p:
        return None
    hyp_p = punctuation_sequence(hypothesis)
    dist = _edit_distance_matrix(ref_p, hyp_p)[-1][-1]
    return 1.0 - dist / len(ref_p)


def extract_numbers(text: str) -> list[float]:
    """All numeric values in the text, digits parsed directly."""
    return [float(m.group(0)) for m in _NUM_IN_TEXT.finditer(text)]


def number_accuracy(
    reference: str,
    hypothesis: str,
    config: NormalizationConfig | None = None,
) -> float | None:
    """Fraction of reference numbers that appear (as words or digits) in the
    hypothesis. Uses number-word expansion so "42" matches "forty two".
    None when the reference contains no numbers."""
    ref_numbers = extract_numbers(reference)
    if not ref_numbers:
        return None
    hyp_text = hypothesis
    if config and config.expand_numbers is False:
        # Even when the global config does not expand numbers, number
        # accuracy is *defined* on canonical word forms (documented).
        hyp_text = _expand_numbers(hyp_text)
    hyp_words = normalize_text(hyp_text, NormalizationConfig(strip_punctuation=True))
    found = 0
    for number in ref_numbers:
        if number in extract_numbers(hyp_text):
            found += 1
            continue
        expected = number_to_words(number)
        if expected in hyp_words:
            found += 1
    return found / len(ref_numbers)


def token_accuracy(reference: str, hypothesis: str, tokens: Iterable[str]) -> float | None:
    """Fraction of the given tokens (entities / technical vocab) present in
    the hypothesis (case-insensitive). None when the token list is empty."""
    wanted = [t for t in (tok.strip() for tok in tokens) if t]
    if not wanted:
        return None
    hyp = re.sub(r"\s+", " ", hypothesis.lower())
    hits = sum(1 for t in wanted if t.lower() in hyp)
    return hits / len(wanted)


STOP_WORDS = frozenset(
    ["a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "has", "have", "i", "in", "is", "it", "its", "of", "on", "or", "that", "the", "this", "to", "was", "were", "will", "with", "you", "your"]
)


def semantic_overlap_proxy(reference: str, hypothesis: str) -> float:
    """Content-word overlap (Jaccard, lowercase, stop-words removed).

    HEURISTIC SIGNAL ONLY — a proxy for semantic preservation, NOT a
    ground-truth metric and NOT an LLM judgment. Always reported under the
    'heuristic' section of the metric report.
    """
    ref_tokens = {
        t for t in re.findall(r"\w+", reference.lower()) if t not in STOP_WORDS
    }
    hyp_tokens = {
        t for t in re.findall(r"\w+", hypothesis.lower()) if t not in STOP_WORDS
    }
    if not ref_tokens:
        return 1.0 if not hyp_tokens else 0.0
    union = ref_tokens | hyp_tokens
    if not union:
        return 1.0
    return len(ref_tokens & hyp_tokens) / len(union)


def timestamp_alignment_error_seconds(
    reference_segments: Sequence[dict[str, float]],
    hypothesis_segments: Sequence[dict[str, float]],
) -> float | None:
    """Mean absolute onset error between best-matching reference/hypothesis
    segment starts. None when either side has no timestamps (never guessed)."""
    if not reference_segments or not hypothesis_segments:
        return None
    errors: list[float] = []
    hyp_starts = sorted(s.get("start", 0.0) for s in hypothesis_segments)
    import bisect

    for ref_seg in reference_segments:
        onset = ref_seg.get("start", 0.0)
        pos = bisect.bisect_left(hyp_starts, onset)
        candidates = [hyp_starts[pos]] if pos < len(hyp_starts) else []
        if pos > 0:
            candidates.append(hyp_starts[pos - 1])
        if candidates:
            errors.append(min(abs(onset - c) for c in candidates))
    if not errors:
        return None
    return sum(errors) / len(errors)


# --- the report -------------------------------------------------------------------


@dataclass
class TranscriptMetrics:
    """Full metric report, separated into ground-truth and heuristic layers."""

    wer: float
    wer_detail: dict[str, int]
    cer: float
    normalization: dict[str, bool]
    # optional component metrics (None = not applicable, honestly reported)
    punctuation_accuracy: float | None = None
    number_accuracy: float | None = None
    entity_accuracy: float | None = None
    technical_vocab_accuracy: float | None = None
    language_correct: bool | None = None
    timestamp_alignment_error_seconds: float | None = None
    realtime_factor: float | None = None
    processing_latency_seconds: float | None = None
    # heuristic layer (never presented as ground truth)
    semantic_overlap_proxy: float | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "ground_truth": {
                "wer": round(self.wer, 4),
                "wer_detail": self.wer_detail,
                "cer": round(self.cer, 4),
                "punctuation_accuracy": _round(self.punctuation_accuracy),
                "number_accuracy": _round(self.number_accuracy),
                "entity_accuracy": _round(self.entity_accuracy),
                "technical_vocab_accuracy": _round(self.technical_vocab_accuracy),
                "language_correct": self.language_correct,
                "timestamp_alignment_error_seconds": _round(
                    self.timestamp_alignment_error_seconds, 3
                ),
                "realtime_factor": _round(self.realtime_factor, 4),
                "processing_latency_seconds": _round(
                    self.processing_latency_seconds, 4
                ),
            },
            "heuristic": {
                # rule-based proxy; NOT a ground-truth metric (see metrics.py)
                "semantic_overlap_proxy": _round(self.semantic_overlap_proxy),
            },
            "normalization": self.normalization,
            "definitions": {
                "wer": "(S+D+I)/reference_words",
                "cer": "char_edit_distance/reference_chars",
                "realtime_factor": "processing_time/audio_duration",
                "semantic_overlap_proxy": "content-word Jaccard (heuristic)",
            },
        }


def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(value, digits)


def compute_transcript_metrics(
    reference: str,
    hypothesis: str,
    *,
    entities: Iterable[str] | None = None,
    technical_vocab: Iterable[str] | None = None,
    reference_language: str | None = None,
    hypothesis_language: str | None = None,
    reference_segments: Sequence[dict[str, float]] | None = None,
    hypothesis_segments: Sequence[dict[str, float]] | None = None,
    processing_time_seconds: float | None = None,
    audio_duration_seconds: float | None = None,
    normalization: NormalizationConfig | None = None,
) -> TranscriptMetrics:
    """Compute the full metric report for one (reference, hypothesis) pair.

    All comparisons run on a normalized copy; the raw strings are also scored
    for punctuation (punctuation is stripped from the normalized copy, so it
    has its own dedicated comparison).
    """
    config = normalization or NormalizationConfig()
    norm_ref = normalize_text(reference, config)
    norm_hyp = normalize_text(hypothesis, config)

    wer, detail = word_error_rate(norm_ref, norm_hyp)
    cer = char_error_rate(norm_ref, norm_hyp)

    lang_ok: bool | None = None
    if reference_language and hypothesis_language:
        lang_ok = reference_language.split("-")[0].lower() == hypothesis_language.split("-")[0].lower()

    rtf: float | None = None
    if processing_time_seconds is not None and audio_duration_seconds:
        rtf = processing_time_seconds / audio_duration_seconds

    return TranscriptMetrics(
        wer=wer,
        wer_detail=detail,
        cer=cer,
        normalization=config.signature(),
        punctuation_accuracy=punctuation_accuracy(reference, hypothesis),
        number_accuracy=number_accuracy(reference, hypothesis, config),
        entity_accuracy=token_accuracy(hypothesis, hypothesis, entities or []),
        technical_vocab_accuracy=token_accuracy(reference, hypothesis, technical_vocab or []),
        language_correct=lang_ok,
        timestamp_alignment_error_seconds=timestamp_alignment_error_seconds(
            reference_segments or [], hypothesis_segments or []
        ),
        realtime_factor=rtf,
        processing_latency_seconds=processing_time_seconds,
        semantic_overlap_proxy=semantic_overlap_proxy(reference, hypothesis),
    )
