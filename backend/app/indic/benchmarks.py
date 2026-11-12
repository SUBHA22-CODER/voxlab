# benchmarks.py
# Benchmark suites and evaluation scoring for Indic speech models (Gnani AI).
# Covers regional languages, code-switching dialects, and Indian named entities.

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from ..speech.metrics import char_error_rate, word_error_rate
from .normalization import (
    detect_code_switch_ratio,
    is_latin_token,
    normalize_indic_text,
)


@dataclass
class IndicBenchmarkItem:
    id: str
    language: str  # e.g. 'hi-IN', 'ta-IN', 'hi-en' (Hinglish)
    category: str  # 'banking', 'ecommerce', 'code_switching', 'numbers_currency', 'named_entities'
    reference_transcript: str
    description: str
    expected_entities: list[str] = field(default_factory=list)
    expected_numbers: list[str] = field(default_factory=list)
    english_loanwords: list[str] = field(default_factory=list)


# Standard Indic benchmark corpus
INDIC_BENCHMARK_CORPUS: list[IndicBenchmarkItem] = [
    # 1. Hindi Customer Support & Banking
    IndicBenchmarkItem(
        id="hi-bank-01",
        language="hi-IN",
        category="banking",
        reference_transcript="कृपया मेरे बचत खाते का बैलेंस बताएं और अंतिम तीन लेनदेन भेजें।",
        description="Hindi savings account balance and mini-statement query",
        expected_entities=["बचत खाता", "बैलेंस"],
    ),
    # 2. Hinglish Code-Switching
    IndicBenchmarkItem(
        id="hi-en-cs-01",
        language="hi-en",
        category="code_switching",
        reference_transcript="Mera refund abhi tak initiate nahi hua hai, please support ticket raise karo.",
        description="Hinglish customer complaint with technical English terms",
        english_loanwords=["refund", "initiate", "support", "ticket"],
    ),
    # 3. Tamil Telecom & Support
    IndicBenchmarkItem(
        id="ta-telecom-01",
        language="ta-IN",
        category="telecom",
        reference_transcript="என் மொபைல் எண்ணிற்கு புதிய டேட்டா ரீசார்ஜ் திட்டங்களை சொல்லுங்கள்.",
        description="Tamil mobile data plan inquiry",
        expected_entities=["மொபைல்", "டேட்டா", "ரீசார்ஜ்"],
    ),
    # 4. Tanglish Code-Switching
    IndicBenchmarkItem(
        id="ta-en-cs-01",
        language="ta-en",
        category="code_switching",
        reference_transcript="Enoda credit card payment decline aaidichu, transaction status check pannunga.",
        description="Tanglish payment issue inquiry",
        english_loanwords=["credit", "card", "payment", "decline", "transaction", "status"],
    ),
    # 5. Telugu E-Commerce
    IndicBenchmarkItem(
        id="te-ecom-01",
        language="te-IN",
        category="ecommerce",
        reference_transcript="నా ఆర్డర్ డెలివరీ తేదీని రేపటికి మార్చగలరా?",
        description="Telugu delivery date reschedule request",
        expected_entities=["ఆర్డర్", "డెలివరీ"],
    ),
    # 6. Benglish Code-Switching
    IndicBenchmarkItem(
        id="bn-en-cs-01",
        language="bn-en",
        category="code_switching",
        reference_transcript="Ami app theke login korte parchi na, OTP receive hocche na.",
        description="Benglish mobile app OTP login issue",
        english_loanwords=["app", "login", "OTP", "receive"],
    ),
    # 7. Numbers, Currency & Indian Units (Lakh, Crore)
    IndicBenchmarkItem(
        id="indic-num-01",
        language="hi-IN",
        category="numbers_currency",
        reference_transcript="कुल राशि पचहत्तर हजार पांच सौ रुपये या ₹75,500 है।",
        description="Hindi numerical currency verification with rupees and thousands",
        expected_numbers=["75500", "75,500"],
    ),
    # 8. Indian Named Entities (Cities, Surnames, Airports)
    IndicBenchmarkItem(
        id="indic-ner-01",
        language="hi-IN",
        category="named_entities",
        reference_transcript="बेंगलुरु से नई दिल्ली के लिए इंडिगो की उड़ान बुक करें।",
        description="Indian airports, airlines, and metro routes",
        expected_entities=["बेंगलुरु", "नई दिल्ली", "इंडिगो"],
    ),
]


@dataclass
class IndicEvaluationReport:
    raw_wer: float
    raw_cer: float
    normalized_wer: float
    normalized_cer: float
    code_switch_ratio: float
    loanword_accuracy: float | None = None
    number_accuracy: float | None = None
    entity_accuracy: float | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_indic_transcription(
    reference: str,
    hypothesis: str,
    expected_loanwords: list[str] | None = None,
    expected_entities: list[str] | None = None,
) -> IndicEvaluationReport:
    """Compute dual evaluation: Raw Metrics (strict verbatim) vs Indic-Normalized Metrics."""
    # 1. Raw WER/CER
    raw_wer, raw_breakdown = word_error_rate(reference, hypothesis)
    raw_cer = char_error_rate(reference, hypothesis)

    # 2. Indic-normalized strings
    norm_ref = normalize_indic_text(reference)
    norm_hyp = normalize_indic_text(hypothesis)
    norm_wer, norm_breakdown = word_error_rate(norm_ref, norm_hyp)
    norm_cer = char_error_rate(norm_ref, norm_hyp)

    # 3. Code-switching loanword accuracy
    loanwords = expected_loanwords or [t for t in reference.split() if is_latin_token(t)]
    loanword_acc: float | None = None
    if loanwords:
        hyp_tokens = set(norm_hyp.split())
        hits = sum(1 for w in loanwords if w.lower() in hyp_tokens)
        loanword_acc = round(hits / len(loanwords), 4)

    # 4. Entity accuracy
    entity_acc: float | None = None
    if expected_entities:
        hits = sum(1 for e in expected_entities if normalize_indic_text(e) in norm_hyp)
        entity_acc = round(hits / len(expected_entities), 4)

    cs_ratio = detect_code_switch_ratio(reference)

    return IndicEvaluationReport(
        raw_wer=round(raw_wer, 4),
        raw_cer=round(raw_cer, 4),
        normalized_wer=round(norm_wer, 4),
        normalized_cer=round(norm_cer, 4),
        code_switch_ratio=cs_ratio,
        loanword_accuracy=loanword_acc,
        entity_accuracy=entity_acc,
        details={
            "raw_substitutions": raw_breakdown["substitutions"],
            "raw_deletions": raw_breakdown["deletions"],
            "raw_insertions": raw_breakdown["insertions"],
            "norm_substitutions": norm_breakdown["substitutions"],
            "norm_deletions": norm_breakdown["deletions"],
            "norm_insertions": norm_breakdown["insertions"],
        },
    )
