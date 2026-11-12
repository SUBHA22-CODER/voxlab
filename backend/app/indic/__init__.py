# __init__.py
# Indic Speech Lab package for VoxLab.

from .normalization import (
    normalize_indic_text,
    normalize_indic_numerals,
    detect_code_switch_ratio,
    is_latin_token,
    is_indic_token,
)
from .benchmarks import (
    INDIC_BENCHMARK_CORPUS,
    IndicBenchmarkItem,
    IndicEvaluationReport,
    evaluate_indic_transcription,
)

__all__ = [
    "INDIC_BENCHMARK_CORPUS",
    "IndicBenchmarkItem",
    "IndicEvaluationReport",
    "detect_code_switch_ratio",
    "evaluate_indic_transcription",
    "is_indic_token",
    "is_latin_token",
    "normalize_indic_numerals",
    "normalize_indic_text",
]

