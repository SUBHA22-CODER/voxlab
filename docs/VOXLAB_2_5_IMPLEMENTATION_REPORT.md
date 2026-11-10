# VoxLab 2.5 — Implementation Report

> Date: 2026-11-11 · Base: VoxLab 2.0 (`37161c5`) → VoxLab 2.5 (`HEAD`)
> Focus: security hardening, a second speech engine, semantic intelligence,
> word-level error localization, robustness analytics, model drift detection,
> database migrations, and dashboard surfaces.

## 1. Existing features reused (not rebuilt)

Everything from 2.0 was preserved and extended in place: the speech engine
abstraction (`app/speech/`), the whisper_local adapter, audio validation,
WER/CER metrics, Darwin audio evolution + minimizer, the regression corpus,
benchmarks, the v1 API surface, all four 2.0 frontend surfaces, CI, and the
ruff governance. The original 109-test baseline remains green inside the
suite. The 2.0 audit documents ([ARCHITECTURE_AUDIT.md](ARCHITECTURE_AUDIT.md))
provided the security worklist executed in Phase 1.

## 2. New features implemented

### Phase 1 — Security hardening (commit `894499f`)
- **Demo credential bypass removed**: every account (including demo)
  authenticates through PBKDF2; `ensure_demo_user` self-heals legacy
  non-canonical demo hashes to the documented credential at startup
  (regression-tested).
- **WebSocket token exposure resolved**: tokens move from `?token=` query
  strings (access-log leak) to the `Sec-WebSocket-Protocol` bearer
  subprotocol; the server selects `"bearer"` and never echoes the token.
- **Token revocation**: JWTs carry `jti`; `RevokedToken` table +
  `POST /api/auth/logout`; `get_current_user` rejects revoked jti
  (jti-scoped: revoking one token leaves siblings valid — tested).
- **Rate limiting generalized** to path-scoped rules: auth 15/min, evolve
  10/min, transcribe 30/min, benchmark 10/min.
- **Audit trail**: `AuditEvent` records login success/failure, register,
  logout (passwords never logged); `GET /api/v1/security/audit` is
  strictly owner-scoped; `GET /api/v1/security/health` reports database,
  auth, retention, and engine status.
- **Audio retention**: `AUDIO_RETENTION_DAYS` (default 30) startup sweep of
  stale artifact directories; 0 disables (documented).
- **Dependencies**: `pip-audit` over `requirements.txt` → **no known
  vulnerabilities** (run 2026-11-11).

### Phase 2 — Second speech engine (commit `9f75425`)
**Vosk** (Kaldi, Apache-2.0) as an independent adapter: honest install and
capability reporting (`streaming_mode: "streaming_decode"` — sequential
decode with carried acoustic state; never claimed as live-mic streaming;
language detection honestly `false` for fixed-language models), model
version tracking via model-dir identity, timeout handling, typed failures,
English-only enforcement with clear rejections, real word timestamps from
Vosk alignments. 6 real integration tests against
`vosk-model-small-en-us-0.15` (~40 MB), including a genuine transcription
assertion and monotonic-timing checks.

### Phase 3 — Semantic error intelligence (commit `620e877`)
Two strictly separated layers:
- **Deterministic (ground truth)** `app/speech/semantic.py`: detects
  meaning-changing substitutions, number errors, date errors, negation
  flips, entity substitutions, technical-terminology errors, missing
  instructions, and intent changes — all reproducible (pinned by a
  determinism test), deduplicated across detectors.
- **LLM (advisory, labeled)** `app/speech/semantic_llm.py`: every judgment
  carries model id, prompt version, prompt hash, temperature (0.0),
  evaluation timestamps, exact input + raw output, and confidence — null
  when the model does not provide one (never guessed). Opt-in via
  `use_llm_judge=true`: transcripts leave the machine only on explicit
  request with a configured key. The layer is unavailable-by-default and
  reports `available: false` honestly.

### Phase 4 — Word-level error localization (commit `620e877`)
`app/speech/alignment.py`: word-level alignment (Levenshtein backtrace)
labeling every token correct/substitution/insertion/deletion with
content-vs-function-word severity. Engine word timestamps (faster-whisper
`word_timestamps=True`) attach ONLY when provided and only when they match
the transcript token-for-token — otherwise dropped rather than misaligned.
`/api/v1/audio/transcribe` returns `alignment`, `semantic`, and (opt-in)
`llm_judgment`; the Audio Lab renders a color-coded word diff with
substitution/insertion/missing legend and an explicit no-timings note when
the engine did not provide them.

### Phase 5 — Robustness heatmap (commit `cf17f0a`)
`GET /api/v1/analytics/robustness` aggregates the user's REAL Darwin audio
findings into condition buckets derived from each finding's actual stored
transform parameters (noise SNR, tape-speed rate, duration) plus persona
aggregation, with engine / model-version / date filters. Untested
conditions are absent, never fabricated (pinned by tests).

### Phase 6 — Model drift detection (commit `cf17f0a`)
- Fixed benchmark dataset: `scripts/build_benchmark_dataset.py` builds
  `core-en-v1` (10 reproducible utterances covering numbers, dates,
  entities, technical vocabulary, negation, question intent, length) from
  committed constants via offline SAPI synthesis.
- `AudioDriftSnapshot`: immutable per-engine/model evaluations.
- Statistics (`app/speech/drift.py`): paired bootstrap CI on mean WER delta
  (2000 rounds, fixed seed, deterministic). A regression is flagged only
  when the CI lower bound > 0; below `MIN_PAIRS = 8` significance is `null`
  with an explicit insufficient-samples note — tiny differences can never
  trigger false alerts (pinned by tests including a noisy +0.01 shift that
  correctly stays unflagged).

### Phase 7 — Database migrations (commit `7b6a89d`)
Alembic (async template) wired to app settings (`ALEMBIC_URL` override for
CI/tests) and the full ORM metadata; autogenerated baseline captures the
complete 21-table schema. Four integrity tests: upgrade creates the full
schema, downgrade drops all user tables, head-upgrade is idempotent, and
ORM `create_all` vs migrated schema are compared so future model changes
force a migration. `create_all` remains for dev convenience; production
uses `alembic upgrade head`.

### Phase 8 — Dashboard (commit `8ed1988`)
- **/analytics** page: robustness heatmap (bucket cards), drift tracking
  (dataset picker, snapshot creation, history, latest-two comparison with
  significance/regression badges), system health cards (database, auth +
  revocation, retention, engines).
- **Audio Lab**: word-level comparison view + semantic error cards with
  severity badges and the ground-truth/advisory labeling.
- Existing visual identity preserved throughout (dark zinc/emerald,
  spotlight cards, Phosphor icons).

## 3. Actual test results (Phase 9, all executed 2026-11-11)

| # | Validation | Command | Result |
|---|---|---|---|
| 1+2 | Full offline suite (incl. the original 109) | `pytest -m "not speech"` | **228 passed**, 0 failed |
| 3 | Real whisper tests | `pytest -m speech` | **7 passed** |
| 4 | Real Vosk tests (second engine) | `pytest -m speech` | **6 passed** (13 total real) |
| 5 | Security tests | `pytest tests/test_security_hardening.py` | **9 passed** |
| 6 | Migration tests | `pytest tests/test_migrations.py` | **4 passed** (round-trip verified) |
| 7 | Frontend build | `npm run build` | clean (strict TS, zero `any`) |
| 8 | Type checking | `tsc` via next build | clean |
| 9 | Linting | `ruff check .` (0.14.4) | **All checks passed** |
| 10 | Browser verification | Browser Use plugin, production build | Analytics page live-verified: robustness state, both datasets, snapshot rows (WER 6.4% whisper / 6.6% vosk), system health — screenshots in `gui-test-screenshots/` |

Mocked vs real: all unit tests use offline stubs; the 13 `speech`-marked
tests run REAL models (faster-whisper tiny + vosk small-en-us) against real
SAPI-synthesized audio. The distinction is preserved in markers, CI jobs,
and this report.

## 4. Benchmark evidence (real runs, 2026-11-11)

Fixed dataset `core-en-v1` (10 cases, SAPI-synthesized):

| Engine / model | Mean WER | Mean CER | Mean RTF | Wall |
|---|---|---|---|---|
| whisper_local / tiny | 0.0350 | — | — | 8.7 s |
| whisper_local / base | 0.0636 | 0.0218 | 0.4017 | ~9 s |
| vosk / small-en-us-0.15 | 0.0661 | 0.0180 | 0.9003 | ~20 s |

Per-case highlights (whisper-tiny): numbers/dates/negation/instructions all
WER 0.00; "VoxLab" → "Vox Lab" cost WER 0.25 on the entity case; vosk
transcribed the full fixture sentence with "VoxLab" → "vox lab". Drift
comparison (whisper-base vs vosk, N=10 paired): mean WER delta +0.0025,
significance computed with the paired-bootstrap CI — an example of the
platform measuring rather than asserting.

## 5. Architecture changes

- New backend packages: `app/speech/{alignment,semantic,semantic_llm,drift}.py`,
  `app/speech/vosk/`, `app/api/v1/{analytics,security}.py`,
  `app/models/{security_models,analytics_models}.py`,
  `app/services/{audit,retention}.py`, `migrations/` (Alembic).
- `app/core/security.py` returns `(token, jti)`; `deps.get_current_user`
  enforces revocation; `app/core/rate_limit.py` is path-scoped.
- Frontend: `lib/audio-types.ts` + `lib/audio-api.ts` extended; new
  `components/audio/word-diff.tsx`; new `(app)/analytics/page.tsx`.
- Dependencies added: `vosk` (optional extra), `alembic` (base).

## 6. Files changed (2.5)

Backend: 24 modified / 15 created. Frontend: 6 modified / 2 created.
CI/docs: lint + ci workflows unchanged from 2.0 governance (ruff, hermetic
CI); docs: this report. Full per-file detail in the git log
(`894499f…HEAD`).

## 7. Known limitations

1. `transcribe` with `word_timestamps` requires the config flag (runtime
   default off) — the UI shows the honest absence note until enabled.
2. Vosk small-en-us is English-only and CPU quantized; accuracy trails
   whisper on some cases (that is exactly what benchmarks are for).
3. Robustness heatmap axes beyond noise/speed/duration (accent, mic
   quality) are currently expressed through personas; dedicated condition
   metadata per finding is future work.
4. Drift datasets live under `AUDIO_STORAGE_DIR` (per-machine); the
   manifest is reproducible from the committed script, but audio itself is
   not committed (TTS-output licensing caution).
5. The GUI click-flow could not drive React handlers inside the in-app
   browser (runtime limitation, documented in 2.0); browser verification
   covered rendering + real backend data, with flows exercised via the API.
6. Rate limiting remains single-process in-memory (documented boundary;
   Redis swap is the stated production path).

## 8. Remaining production risks

- Pre-existing items intentionally preserved for compatibility: 7-day JWT
  lifetime without refresh rotation; single-worker task registry (cancellation
  does not survive restarts); SQLite default storage (Postgres supported).
- `pip-audit` is clean today; add it as a CI gate (security.yml already
  runs weekly) for continuous enforcement.
- The bootstrap CI needs ≥ 8 paired cases for significance; smaller
  datasets report deltas without claims (by design, but operators must
  build adequate datasets before trusting drift verdicts).
