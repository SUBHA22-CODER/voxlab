# VoxLab Audio Engine Guide

> VoxLab 2.0 · Speech engine abstraction, audio validation, and the whisper_local adapter

## Installation

The platform runs fully without the speech stack (engines are reported as not
installed). To enable real transcription:

```bash
cd backend
pip install -r requirements-speech.txt
```

This installs `faster-whisper` (CTranslate2 runtime), `numpy`, and `soxr`.
Models download from HuggingFace on first use and are cached afterwards:

| Model | First-run download | Notes |
|---|---|---|
| `tiny` | ~75 MB | Default for tests/demo |
| `base` | ~141 MB | Platform default (`SPEECH_WHISPER_MODEL`) |
| `small` / `medium` / `large-v3` | ~465 MB / ~1.5 GB / ~3 GB | Higher accuracy |

Configuration (env or `backend/.env`): `SPEECH_WHISPER_MODEL`, `SPEECH_DEVICE`
(`cpu` default, `cuda` only when explicitly configured), `SPEECH_COMPUTE_TYPE`
(`int8` default), `SPEECH_TIMEOUT_SECONDS`, `SPEECH_MAX_UPLOAD_MB` (25),
`SPEECH_MAX_DURATION_SECONDS` (600), `AUDIO_STORAGE_DIR` (`./data/audio`).

## Supported audio formats

| Format | Decoder | Notes |
|---|---|---|
| WAV (PCM 8/16/32-bit) | stdlib `wave` | Always available |
| MP3, FLAC, OGG, WebM, M4A | PyAV (`av`, bundled with faster-whisper) | Requires the speech extra |
| 24-bit WAV | not supported | Re-encode as 16/32-bit |

Every upload is validated: size cap, duration cap, corruption (truncated
containers, NaN samples), sample alignment. Failures raise typed exceptions
that map to honest HTTP codes (413 too large, 422 unsupported/corrupt).

The engine contract is **mono float32 at 16 kHz**. Multi-channel audio is
downmixed by averaging; other rates are resampled with soxr. Peak
normalization is opt-in per call and always disclosed in the response
metadata — the original audio is never silently modified.

## Engine interface

Every engine implements `app/speech/base.py::SpeechEngine`:
`initialize / health_check / transcribe / transcribe_stream / get_capabilities
/ get_metadata / shutdown`. The registry (`app/speech/registry.py`) reports
every known engine with honest install status; `GET /api/v1/engines` exposes
it. Uninstalled engines return 503 with the install hint — never a fake
error transcription.

## Streaming honesty

faster-whisper has no true streaming decoder (whisper-local itself uses a
separate sherpa-onnx engine for that). VoxLab's `transcribe_stream()` is a
**chunked sliding window** (25% overlap) producing real progressive
partials, labeled `streaming_mode: "chunked_window"` in capabilities. The
platform never claims sub-word realtime streaming.

## Adding a new engine

1. Subclass `SpeechEngine` in `app/speech/<engine>/adapter.py`.
2. Implement `engine_id()`, `is_available()` (import probe), and the
   transcription surface. `TranscriptionResult` carries only what the engine
   actually produced — timestamps and speaker labels are never fabricated.
3. Register it in `registry.build_default_registry()`.
4. Add capability-truthfulness tests (see `tests/test_speech_audio.py`).

## Attribution

The whisper_local adapter is adapted from
[drajb/whisper-local](https://github.com/drajb/whisper-local) (MIT):

```
Copyright (c) 2025 Pin Wang (original whisper-key-local)
Copyright (c) 2026 Rohit Burani (whisper-local fork and modifications)
```

Patterns carried over: the mono-float32/16 kHz contract, load-once + warmup,
explicit last-error reporting ("no speech" ≠ runtime failure), model size
hints, and CUDA fail-fast. The attribution is embedded in the adapter
module and surfaced by `GET /api/v1/engines`.
