# Evaluation Metrics (Transcription)

> VoxLab 2.0 · `backend/app/speech/metrics.py` — the ground-truth layer

## Definitions (fixed, documented)

| Metric | Definition | Notes |
|---|---|---|
| **WER** | (S + D + I) / reference word count | Full backtrace; can exceed 1.0 on insertions (documented) |
| **CER** | character edit distance / reference char count | Spaces included, matching common practice |
| **RTF** | processing time / audio duration | Real-time factor; lower is better |
| **Punctuation accuracy** | 1 − edit distance over punctuation sequences | N/A when the reference has none |
| **Number accuracy** | share of reference numbers found (digits or words) | "42" matches "forty two" by canonical expansion |
| **Entity accuracy** | share of provided entities present in the hypothesis | Case-insensitive |
| **Technical vocab accuracy** | share of provided vocabulary present | Case-insensitive |
| **Language correctness** | reference language == detected language | N/A unless both are provided |
| **Timestamp alignment** | mean absolute onset error vs reference segments | N/A unless reference segments exist |

Empty reference: WER/CER are 0.0 only when the hypothesis is empty too;
otherwise 1.0. A silent clip transcribing to "" is a valid result, never an
error.

## Normalization is configurable, never silent

`NormalizationConfig` controls, per comparison: lowercase, punctuation
stripping, contraction expansion, **number expansion** ("25" ↔ "twenty five"
only when `expand_numbers=True`), filler removal, unicode folding. Every
metric report records which rules were applied, so two scores are only
comparable when their normalization signatures match.

Darwin Audio and benchmarks default to `expand_numbers=True` (documented
choice: spoken/digit equivalence is the point of number stress tests).

## The two honesty layers

Every metric report has two sections:

1. `ground_truth` — deterministic text comparisons above. These are real
   metrics.
2. `heuristic` — `semantic_overlap_proxy` (content-word Jaccard). A rule-
   based proxy. It is never presented as a ground-truth metric, and any
   future LLM-based semantic judge must be labeled separately with its model
   and configuration (per the master spec: an LLM judgment is not ground
   truth).

## API surface

`POST /api/v1/audio/transcribe` with `reference_transcript` (+ optional
`entities`, `technical_vocab`) returns the full report under `metrics`.
The frontend Audio Lab renders it as bars with N/A where a component does
not apply — missing data is displayed as missing, never as zero.
