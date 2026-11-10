# Benchmarking (Multi-Engine Speech)

> VoxLab 2.0 · Identical conditions, honest gaps

## Method

`POST /api/v1/benchmarks/audio` runs **the same clip** through every
requested engine under identical conditions: identical decoded audio,
identical reference transcript, identical normalization
(`expand_numbers=True`), identical metric definitions. Nothing varies
between engines except the engine.

| Measured | Source |
|---|---|
| WER / CER | `app/speech/metrics.py` against the reference |
| Processing time | engine-reported `processing_time_seconds` |
| Real-time factor | processing time / audio duration |
| Language + probability | engine-reported detection |
| Text output | verbatim engine result |

## Honesty rules

- Unknown engine ids → 422 with the known list.
- Installed-but-unavailable engines (e.g. runtime missing at call time) →
  `{"status": "error", "error": ...}` for that engine only.
- Known-but-not-installed engines → `{"status": "not_installed",
  "install_hint": ...}` — a benchmark with one installed engine still works
  and reports the others as gaps.
- With no reference transcript, WER/CER are omitted (no fabricated
  rankings on text similarity alone).
- No aggregate "winner" is invented server-side; the UI marks best WER
  among engines that actually returned metrics.

## Persistence & UI

Each run persists as an `AudioBenchmark` (per-engine results JSON) and is
browsable at **Benchmarks** in the dashboard: per-engine cards with output,
metric line (WER / RTF / ms / model), best-WER marker, and history for
trend comparison across engine or model upgrades.
