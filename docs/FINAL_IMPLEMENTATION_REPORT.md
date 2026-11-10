# VoxLab 2.0 — Final Implementation Report

> Date: 2026-11-11 · Base: `9bd93ef` (P0 MVP) → `6a3588b` (VoxLab 2.0)
> Execution of the master engineering prompt: real speech recognition,
> audio adversarial evolution, measurable evaluation, regression corpus,
> multi-engine benchmarking, v1 API, and frontend surfaces.

## 1. Original architecture (summary)

VoxLab was a text-only voice-agent reliability platform: FastAPI backend
(9 routers, async SQLAlchemy, SQLite/Postgres), Darwin text-fuzzing engine
(genomes → scripted conversations → T/Q/R/L/E scoring → ddmin minimization →
diagnosis → patch proposals → regression scenario export), two demo agents,
and a Next.js 16 dashboard. Server-side audio did not exist: STT happened
in the browser (Web Speech API) and `HTTPAgentAdapter.send_audio` raised
`NotImplementedError`. Full detail: [ARCHITECTURE_AUDIT.md](ARCHITECTURE_AUDIT.md).

## 2. Secondary repository audit (`drajb/whisper-local`)

Verified before any integration (2026-11-10): exists (178★, v0.24.0,
pushed 2026-11-07), **MIT licensed** (Pin Wang + Rohit Burani dual
copyright), implementation matches documentation (`faster-whisper`,
`ctranslate2`, `soxr`, `sherpa-onnx`), 5,128-line smoke-test suite. It is
a desktop dictation app, so its **transcription core** was adapted, not the
app: the mono-float32/16 kHz contract, load-once + warmup, explicit
last-error channels, model registry/cache checks, size hints, CUDA
fail-fast. Attribution is retained in the adapter module, the docs, and the
public engines API. Detail: [INTEGRATION_PLAN.md](INTEGRATION_PLAN.md).

## 3. Integrated modules & new features

| Area | Implementation |
|---|---|
| Engine abstraction | `SpeechEngine` ABC, typed results/exceptions, registry with honest install detection (`app/speech/`) |
| Audio validation | WAV (stdlib) + MP3/FLAC/OGG/WebM (PyAV); size/duration/corruption checks; soxr resampling; opt-in normalization |
| Real STT | `whisper_local` faster-whisper adapter: CPU-first int8, warmup, timeouts, chunked-window streaming (honestly labeled), capabilities/metadata |
| Metrics | WER (S/D/I backtrace), CER, configurable normalization, number/entity/vocab/punctuation accuracy, RTF, timestamp alignment; heuristic layer separated (`app/speech/metrics.py`) |
| Audio attacks | 14 seeded, bounds-checked transform operators + offline SAPI TTS for seed/content mutation |
| Darwin Audio | 10 personas, genome content-hashing, async materialization, weighted failure fitness with anti-noise gates, selection/breeding, 60-session hard budget, per-evaluation atomic commits |
| Minimization | ddmin over transform chains; acceptance requires real failure reproduction |
| Regression corpus | Persistent cases with minimized chains, replay classification (fixed/improved/still_failing), owner-scoped deletion |
| Benchmarking | Same-audio multi-engine comparison; not-installed engines reported as gaps; no fabricated rankings |
| API v1 | `/api/v1/engines`, `/engines/{id}/health`, `/audio/transcribe`, `/darwin/audio/*`, `/regressions*`, `/benchmarks/audio` — existing `/api/*` untouched |
| Frontend | Audio Lab, Darwin Audio Lab (live progress, diff view, chain minimization), Benchmarks, Regression Corpus; typed v1 client; existing design language extended |
| CI | Hermetic base suite (`-m "not speech"`), opt-in real-engine job (workflow_dispatch), pinned ruff 0.14.4 with `ruff.toml` |

## 4. Files & dependencies

- **Created:** `backend/app/speech/` (11 modules), `backend/app/darwin_audio/` (8),
  `backend/app/api/v1/` (5), `backend/app/models/darwin_audio.py`,
  `backend/app/core/limits.py`, `backend/app/schemas/audio.py`,
  `backend/requirements-speech.txt`, `backend/ruff.toml`,
  `backend/scripts/audio_darwin_demo.py`, 6 new test files,
  5 frontend modules, 5 docs + this report.
- **Modified:** `app/main.py` (v1 mount), `app/api/darwin.py` +
  `app/darwin/evolution.py` (budget dedup), `app/darwin/regression.py`
  (test-isolation override), `app/models/__init__.py` (model registration),
  `app/core/config.py` (speech settings), `pytest.ini` (speech marker),
  `requirements.txt` (python-multipart, arq), workflows, sidebar nav,
  `components/ui.tsx` (CardHeader right slot).
- **Removed:** nothing (zero existing functionality deleted).
- **Dependencies added:** `faster-whisper`, `numpy`, `soxr`
  (optional extra); `python-multipart`, `arq` (base, previously missing).

## 5. Test execution results (actual runs)

| Suite | Command | Result |
|---|---|---|
| Baseline (pre-change) | `pytest -q` | **109 passed** in 14.56 s |
| Offline suite (final) | `pytest -m "not speech"` | **184 passed**, 0 failed |
| Real-engine suite | `pytest -m speech` | **7 passed** in ~90 s (tiny model, CPU) |
| Frontend build | `npm run build` | compiles clean (strict TS, zero `any`) |
| Lint | `ruff check .` | **All checks passed** (ruff 0.14.4, configured) |

Real vs mocked coverage: all engine-path unit tests use offline stubs;
`tests/test_whisper_local_integration.py` runs the **real faster-whisper
tiny model** against real SAPI-synthesized speech (transcription content,
number recognition, silence handling, streaming partials, timestamps,
capabilities truthfulness). CI keeps these separated; the distinction is
preserved everywhere.

## 6. Real failure-discovery evidence

`scripts/audio_darwin_demo.py` (whisper-tiny, CPU, 17.3 s wall, 8/8 budget):

```
reference:  "Schedule the kubernetes deployment for order forty two on Friday"
heard:      "Schedule the comparison to boyless 440Q on Friday."
WER 0.60 · CER 0.53 · technical_vocab 0.0 · number "forty two" → "440Q"
minimized chain: 4 → 3 transforms (tape_speed 1.35× + telephony_bandpass + echo)
failure reproduced after minimization; WAV artifact + replay record stored
```

Four distinct findings were produced in one run (pop 4 × gen 2, threshold
0.35). This is the platform's core promise working on real audio with a
real engine.

## 7. Security review

- Speech stack is fully local/offline; no audio ever leaves the machine
  (no external STT/LLM calls for audio).
- Uploads: size + duration caps, typed rejection, hex-id artifact addressing
  with path-traversal validation; artifacts gitignored under `AUDIO_STORAGE_DIR`.
- Owner scoping on every v1 route (runs, findings, regressions, benchmarks);
  deletion is owner-only.
- Budget cap single-sourced and engine-enforced (never bypassed).
- Pre-existing items intentionally preserved (backward compatibility) and
  flagged in the audit: demo-credential bypass (`demo123`/`demo1234`),
  WS token in query string, 7-day JWT without revocation, in-memory rate
  limiting. These are queued as the next hardening pass.
- Fixed during this work: test suite no longer writes into tracked
  fixtures; missing `arq` dependency added; budget-cap duplication removed.

## 8. Known limitations

1. Only one engine (whisper_local) is installed; the benchmark surfaces are
   built for many and report others as `not_installed` honestly.
2. Streaming is chunked-window, not sub-word realtime (faster-whisper has
   no streaming decoder; whisper-local uses a separate model for that).
3. Offline TTS (SAPI) is Windows-only; content personas degrade honestly
   elsewhere; seed audio can always be uploaded instead.
4. New tables are additive via `create_all`; existing deployments get them
   at next startup, but there is no Alembic migration path yet.
5. 24-bit WAV input is rejected with a clear re-encode message.
6. The GUI file-upload flow could not be exercised through the in-app
   browser (upload unsupported by that runtime); it is covered by the real
   engine integration tests at the API layer.

## 9. Installation & example commands

```bash
# backend + speech stack
cd backend && python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt -r requirements-speech.txt
python -m uvicorn app.main:app --port 8001

# demo agents (unchanged)
cd agent-examples/customer-support-agent && python -m uvicorn main:app --port 8100
cd agent-examples/dictation-agent && python -m uvicorn main:app --port 8200

# frontend
cd frontend && npm install && npm run dev   # http://localhost:3000

# real failure-discovery demo (tiny model, CPU)
cd backend
.venv\Scripts\python.exe scripts\audio_darwin_demo.py --model tiny --population 4 --generations 2

# tests
pytest -m "not speech"   # hermetic suite
pytest -m speech         # real engine (downloads tiny model on first run)
```

## 10. Feature verification matrix

| Feature | Implemented | Tests passed | Evidence |
|---|---|---|---|
| Speech engine adapter | ✅ | 16 offline + 7 real | `app/speech/*`, `test_speech_audio.py`, `test_whisper_local_integration.py` |
| Real transcription | ✅ | 7 real-engine | tiny-model transcription of SAPI speech; content + numbers verified |
| Darwin audio mutations | ✅ | 21 offline | `test_darwin_audio_genome.py` (determinism, bounds, lineage) |
| WER/CER | ✅ | 17 offline | `test_speech_metrics.py` (definition pins) |
| Delta debugging | ✅ | 2 focused + run-level | `test_darwin_audio_evolution.py` (minimizer honesty) |
| Regression corpus | ✅ | API tests | promote/replay/classify/delete endpoints |
| Multi-engine benchmark | ✅ | API tests | identical-conditions comparison, honest gaps |
| API integration | ✅ | 15 API tests | `test_api_v1_audio.py` (auth, validation, payloads) |
| Dashboard | ✅ | build + GUI pass | 4 surfaces verified in-browser (screenshots in `gui-test-screenshots/`) |
| Security controls | ✅ | audit + fixes | owner scoping, caps, traversal-safe storage, budget single-source |
| Existing functionality preserved | ✅ | 109 baseline tests unchanged | `9bd93ef` suite still green inside the 184 |

## 11. Suggested next steps

1. Second engine adapter (e.g. faster-whisper `int8_float16` on CUDA, or a
   Parakeet adapter) to make benchmarks two-way.
2. Alembic migrations for the new tables on existing deployments.
3. LLM-labeled semantic judge (labeled separately from ground truth) for
   deeper meaning-preservation scoring.
4. WebSocket PCM16 streaming fuzzing (the text Darwin roadmap item), now
   unblocked by the engine layer.
5. Hardening pass on the pre-existing auth items flagged in §7.
