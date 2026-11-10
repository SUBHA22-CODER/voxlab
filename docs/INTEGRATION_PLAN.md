# VoxLab 2.0 Integration Plan — Whisper Local Speech Engine

> Date: 2026-11-10 · Reference repo audit commit: `master` @ 2026-11-07 (v0.24.0)

## 1. Secondary repository audit: `drajb/whisper-local`

Verified before any integration work (per the Phase-0 mandate):

| Check | Result |
|---|---|
| Accessible | ✅ https://github.com/drajb/whisper-local (178 ⭐, Python, 3.8 MB) |
| License | ✅ **MIT** — dual copyright: "Copyright (c) 2025 Pin Wang (original whisper-key-local)" + "Copyright (c) 2026 Rohit Burani (whisper-local fork and modifications)". VoxLab is also MIT → reuse permitted **with attribution retained** |
| Implementation matches docs | ✅ `pyproject.toml` declares `faster-whisper>=1.2.1`, `ctranslate2==4.7.1`, `numpy`, `soxr`, `sherpa-onnx`, `sounddevice`, `ten-vad`; source in `src/whisper_key/` implements exactly that |
| Tests | ✅ `tests/test_smoke.py` — 5,128 lines of smoke tests (large, serious suite) |
| Actively maintained | ✅ pushed 2026-11-07, CHANGELOG at v0.24.0 |

### What whisper-local actually is

A **desktop push-to-talk dictation app** (Windows/macOS tray app, hotkeys,
clipboard injection, per-app rules) — **not** a library or service. Therefore
"integrating whisper-local" means **adapting its speech-recognition core**, not
embedding the app. The relevant modules:

| Module | Lines | Role | Reuse value |
|---|---|---|---|
| `whisper_engine.py` | 334 | `WhisperEngine` wrapper around `faster_whisper.WhisperModel`: load-once + warmup, async model switching, VAD pre-check, GPU runtime verification, `transcribe_audio(mono float32 @ 16 kHz) -> text` | **High** — the core transcription contract we mirror |
| `model_registry.py` | 162 | Model → HuggingFace repo/local path resolution, HF cache detection | **High** — pattern for model availability checks |
| `voice_activity_detection.py` | 299 | VAD gate to short-circuit silent audio before a full decode | **Medium** — optional pre-check in adapter |
| `streaming_recognizer.py` | 150 | True streaming via sherpa-onnx zipformer (a *different* engine than Whisper) | **Reference only** — honest streaming claims for Whisper are chunked-window, see §4.2 |
| `audio_gain.py`, `noise_suppression.py`, `audio_recorder.py` | — | Capture-side concerns (mic, AGC, RNNoise) | **Not reused** — VoxLab tests *existing* audio, it does not capture from a mic |
| `dictation_cleanup.py` | 275 | Text post-processing (fillers, self-corrections) | **Not needed** — VoxLab's dictation-agent already implements equivalent cleanup; duplicating it would violate "no duplicate modules" |

### Quality assessment

The code is production-quality for its purpose: explicit error channels
(`last_error` distinguishes "no speech" from real failures), warmup to avoid
first-inference latency, background model loading with progress callbacks, CUDA
library fail-fast (issue #15 lesson: cuBLAS/cuDNN absence hangs first inference,
it does not error), careful comments explaining *why*. No fabricated results.

### Key technical contract extracted

```
input:  np.ndarray, mono, float32, 16_000 Hz
output: plain text ("" / None when no speech); segments carry start/end timestamps
        info.language + info.language_probability from faster-whisper
errors: surfaced explicitly, never silently mapped to "no speech"
```

## 2. Licensing & attribution plan

1. VoxLab keeps its MIT `LICENSE`.
2. `backend/app/speech/whisper_local/` carries a module docstring crediting
   whisper-local (Pin Wang / Rohit Burani) as the reference implementation and
   linking both copyright lines.
3. `docs/AUDIO_ENGINE_GUIDE.md` repeats the attribution.
4. No whisper-local source is copied verbatim wholesale; patterns are adapted to
   VoxLab's async service architecture (the original is a synchronous desktop
   component).

## 3. Target architecture (adapted to the existing tree)

The master prompt proposes `voxlab/engines/…`; VoxLab already has
`backend/app/engine/` (scenario/evaluation engine — a *different* concept), so
the speech stack lives in **`backend/app/speech/`** to avoid a name collision:

```
backend/app/speech/
├── __init__.py
├── base.py                  # SpeechEngine ABC + TranscriptionResult/EngineInfo dataclasses
├── audio.py                 # decode/validate WAV/MP3/FLAC/OGG → mono float32 16 kHz
├── exceptions.py            # AudioValidationError, EngineNotAvailable, EngineTimeout…
├── metrics.py               # WER, CER, normalization, entity/number accuracy (Phase 3)
├── transforms.py            # reproducible audio attack transformations (Phase 4)
├── registry.py              # engine discovery/registry (installed vs available)
└── whisper_local/
    ├── __init__.py
    ├── adapter.py           # WhisperLocalEngine(SpeechEngine) via faster-whisper
    └── config.py            # model key, device, compute_type, beam, VAD toggle
```

New engine-adjacent modules (Phases 4–7):

```
backend/app/darwin_audio/      # audio evolution loop, fitness, minimizer, corpus
backend/app/api/v1/            # versioned routes (audio, darwin-audio, regressions, benchmarks)
```

## 4. Design decisions

### 4.1 Dependencies

| Package | Why | Where |
|---|---|---|
| `faster-whisper>=1.2.1` | The actual STT engine (CTranslate2 runtime) | `backend/requirements-speech.txt` (optional extra) |
| `soxr>=0.3.0` | High-quality resampling to 16 kHz (same choice whisper-local made) | `requirements-speech.txt` |
| `numpy>=1.24` | Audio array contract | `requirements-speech.txt` (transitively required anyway) |

**Why optional:** AGENTS.md forbids mandatory external dependencies for basic
functionality and requires deterministic fallbacks; the platform (auth, agents,
text Darwin, all 109 existing tests) must work without the speech stack. The
registry reports `installed: false` honestly when faster-whisper is absent.
Docker images and the dev venv install the extra; lightweight CI does not.

**Format decoding:** WAV via stdlib `wave` (zero deps). MP3/FLAC/OGG via PyAV
(`av`), which is *already* a faster-whisper dependency — no new package needed;
`audio.py` degrades with a clear error when `av` isn't importable.

### 4.2 Streaming honesty

whisper-local's true streaming comes from a **sherpa-onnx zipformer**, not from
Whisper. faster-whisper transcribes a complete buffer. VoxLab's
`transcribe_stream()` therefore implements a **chunked sliding-window** mode
(real progressive output, honestly labeled `streaming_mode: "chunked_window"` in
capabilities) — the platform will never claim sub-word realtime streaming.

### 4.3 Engine interface (Phase 1)

```python
class SpeechEngine(ABC):
    async def initialize() -> None
    async def health_check() -> EngineHealth
    async def transcribe(audio: AudioData, language: str | None) -> TranscriptionResult
    def transcribe_stream(audio: AudioData, chunk_seconds: float) -> Iterator[PartialTranscription]
    def get_capabilities() -> EngineCapabilities   # languages, streaming_mode, timestamps…
    def get_metadata() -> EngineMetadata           # name, version, model, device
    async def shutdown() -> None
```

`TranscriptionResult` normalizes: engine id, text, language + probability,
segments (start/end — only when the engine provides them; **never fabricated**),
duration, processing time, model/device metadata. CPU-only by default
(`device: "cpu"`, `compute_type: "int8"`); CUDA used only when explicitly
configured and verified (following whisper-local's fail-fast lesson).

### 4.4 What plugs where

| Phase | New capability | Touches |
|---|---|---|
| 1 | Engine abstraction + audio validation + registry | `app/speech/*` (new) |
| 2 | Whisper adapter + real transcription endpoint | `app/speech/whisper_local/`, `api/v1/audio.py` |
| 3 | WER/CER + normalization + entity metrics | `app/speech/metrics.py` |
| 4 | Darwin audio evolution (22 attack transforms, personas, fitness) | `app/speech/transforms.py`, `app/darwin_audio/` |
| 5 | ddmin over transformation chains | `app/darwin_audio/minimizer.py` |
| 6 | Regression corpus (DB models + replay + version compare) | `app/models/audio_regression.py`, `api/v1/regressions.py` |
| 7 | Multi-engine benchmark | `app/darwin_audio/benchmark.py`, `api/v1/benchmarks.py` |
| 8 | Dashboard surfaces | `frontend/src/app/(app)/audio`, `benchmarks`, `regressions` |

### 4.5 Model strategy

- Default model: `base` (int8, ~74 MB on disk) — configurable via
  `SPEECH_WHISPER_MODEL` env (`tiny`…`large-v3`, `.en` variants, local paths).
- Models download from HuggingFace on first use (same repo ids as whisper-local /
  Systran faster-whisper). Never in CI by default; CI model tests are opt-in via
  workflow_dispatch with `SPEECH_TESTS_ENABLED=1`.
- Real integration fixtures: small CC0/public-domain speech clips generated
  offline for tests; no private recordings ever committed (AGENTS.md + prompt §8).

### 4.6 Risks & mitigations

| Risk | Mitigation |
|---|---|
| `create_all` can't migrate existing DBs (audit L8) | New 2.0 tables are additive with new names; startup `create_all` handles fresh installs; migration notes documented for existing deployments |
| Heavy model download surprises users | Size hints surfaced in API metadata + docs (pattern taken from whisper-local `_MODEL_SIZE_HINTS`) |
| GPU claims | Device autodetection reports honestly; default is CPU int8; no GPU claims in docs until tested (prompt rule 11) |
| Privacy | Audio artifacts stored under `backend/data/audio/` (gitignored), user-scoped, deletion endpoint; no audio ever sent to external LLM providers (prompt §12) |
