# Regression Testing (Audio Corpus)

> VoxLab 2.0 · Persistent, replayable transcription-failure cases

## What a case is

An `AudioRegressionCase` row (`app/models/darwin_audio.py`) stores everything
needed to reproduce a failure **without the original run**:

```
test_id (hex) · engine · model_version · language · severity · failure_category
seed_audio_ref (stored WAV) · transform chain (operators + params + seeds)
reference_transcript · expected_behavior · baseline metrics (WER/CER) · tags
```

Cases are created by promoting a Darwin Audio finding
(`POST /api/v1/regressions/from-finding/{finding_id}`); the minimized chain
is stored so replays are cheap and exact.

## Replay

`POST /api/v1/regressions/{id}/run` re-runs the stored chain through the
live engine right now and classifies the outcome at documented thresholds:

| Replay WER | Classification |
|---|---|
| ≤ 0.10 | `fixed` — the engine now handles this clip |
| ≥ 0.5 × baseline WER | `still_failing` |
| otherwise | `improved` |

Every replay records engine + model + timestamp on the case (`last_run`),
so the corpus answers the core product question: **is this failure still
present, and did a fix regress?**

## Organization & privacy

Cases are owner-scoped (user FK), filterable by engine and severity
(critical / high / medium / low, derived from baseline WER), and deletable
by their owner (`DELETE /api/v1/regressions/{id}` — privacy-aware deletion).

Seed audio lives under `AUDIO_STORAGE_DIR`, addressed by strictly validated
hex ids (path-traversal safe). **No private recordings are committed to the
repository**; the tracked `scenarios/regression/*.json` files remain
text-mode Darwin conversation cases, and the test suite writes its exports
to `tmp_path` only.
