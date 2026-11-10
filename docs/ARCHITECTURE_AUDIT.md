# VoxLab Architecture Audit (VoxLab 2.0 Phase 0)

> Date: 2026-11-10 · Baseline commit: `9bd93ef` · Baseline test result: **109 passed / 0 failed** (`pytest -q`, 14.56 s — see [BASELINE_TEST_REPORT.md](BASELINE_TEST_REPORT.md))

This document records the state of the VoxLab repository **before** the VoxLab 2.0
(real speech engine + audio adversarial testing) integration. It is the reference
for what must remain backward compatible and where the new engine plugs in.

---

## 1. What VoxLab is today

VoxLab is a **voice-agent reliability platform**: it runs adversarial conversational
scenarios against HTTP/WebSocket voice agents, evaluates transcripts with a
weighted score (T/Q/R/L/E), evolves adversarial "genomes" with a genetic engine
(**Darwin**), minimizes failing conversations via **ddmin**, diagnoses root causes,
proposes config patches, and exports minimized failures into a regression
scenario library.

**Critical finding for this integration:** the current platform is **text-only on
the server side**. There is no audio decoding, no server-side STT, no speech
engine anywhere in `backend/app`:

| Component | Location | Status |
|---|---|---|
| Browser STT (Web Speech API) | `frontend/src/lib/speech.ts` | Real, client-side only |
| `voice_transcript` WS frame | `backend/app/api/playground.py:119-140` | Text arrives **already transcribed** by the browser; backend records `audio_received`/`stt_completed` events with `provider: "browser_web_speech"` |
| `SpeechEngine.send_audio` | `backend/app/adapters/base.py:44-47` | Abstract method exists |
| HTTP adapter `send_audio` | `backend/app/adapters/http_adapter.py:93-98` | **`raise NotImplementedError("HTTP adapter accepts text turns only in MVP")`** |
| WS adapter `send_audio` | `backend/app/adapters/websocket_adapter.py:85-90` | Raw binary passthrough, no decoding |
| `EVENT_TTS_COMPLETED` | `backend/app/engine/trace_collector.py:24` | Defined, never recorded |

## 2. Architecture inventory

### 2.1 Backend (`backend/app/`)

- **Entry** (`main.py`): FastAPI v0.1.0, lifespan runs `init_db()` (`create_all`) +
  builtin scenario seeding; CORS (`*.onrender.com`, `*.vercel.app`, localhost);
  auth rate-limit middleware (15 req/60 s on `/api/auth`).
- **Routers** (`api/`): `auth`, `agents` (SSRF-guarded registration, Fernet-encrypted
  credentials, connect probe), `scenarios`, `test-runs` (202 + queue dispatch),
  `sessions`, `traces`, `reports` (+ compare), `darwin`, `playground` (WebSocket).
- **Core** (`core/`): async SQLAlchemy; default `sqlite+aiosqlite:///./voxlab.db`
  with WAL + `busy_timeout=60000`; Postgres via `asyncpg` supported. Settings via
  pydantic-settings (`.env`); JWT HS256 (7-day tokens); PBKDF2-SHA256 (240k iters);
  Fernet for agent credentials; in-memory sliding-window rate limiter.
- **Models** (`models/`): `User`, `Agent`, `Scenario`, `TestRun`, `Session`,
  `Event`, `Trace`, `Evaluation`, `Report`; darwin models `DarwinRun`,
  `DarwinGeneration`, `DarwinFinding`.
- **Engine** (`engine/`): `scenario_runner` (step types: message, interrupt,
  tool_failure, silence), `evaluation_engine` (deterministic checks → LLM judge →
  transcript similarity; heuristic fallbacks when no LLM key), `orchestrator`
  (in-process asyncio; ARQ queue when `REDIS_URL` set), `reports` (transparent
  0.30T + 0.25Q + 0.20R + 0.15L + 0.10E), `trace_collector` (stage timings,
  marked `"illustrative": true`), `adapters/` (HTTP via httpx, WebSocket).
- **Darwin** (`darwin/`): `evolution.py` (seeded GA loop, budget clamp
  `DARWIN_MAX_SESSIONS` default **60**, per-session incremental commits, dedup by
  genome hash), `genome.py` (sha256-12 genome ids, 4 mutation operators +
  crossover), `personas.py` (7 active, 3 stubs), `attacker.py` (LLM-driven or
  deterministic heuristic bank), `fitness.py` (dictation-aware blend), `minimizer.py`
  (classic ddmin, capped evaluations), `diagnoser.py` (14 rule-based categories,
  LLM refinement optional), `patcher.py` (failure-config diff proposal + sandbox
  verify via `metadata.failure_config`), `regression.py` (export to
  `scenarios/regression/*.json` + Scenario row).
- **Services** (`services/`): `LLMService` (real OpenAI-compatible client when a
  key exists; `available` property; graceful `None` fallback), `endpoint_guard`
  (SSRF protection).

### 2.2 Demo agents (`agent-examples/`)

- **customer-support-agent** (:8100): scripted deterministic brain + optional LLM
  mode; four deliberately-broken failure switches (`ignore_interruptions`,
  `crash_on_tool_error`, `forget_context`, `hinglish_support=false`, …). Text-only.
- **dictation-agent** (:8200): **regex text-cleanup pipeline** (self-correction
  resolution, filler stripping, spoken punctuation, name mangling). Accepts
  `metadata.failure_config` override — this is what makes Darwin's patch
  verification work. **It does not process audio**; it cleans pre-transcribed text.

### 2.3 Frontend (`frontend/`)

Next.js 16 / React 19 / Tailwind 4 / recharts 3. App-router pages: dashboard,
agents (+new), scenarios, runs (+detail), reports, traces, playground (WS), darwin
(+detail), unified animated `/register` auth. `lib/api.ts` typed client (base URL
`NEXT_PUBLIC_API_URL`, token in localStorage, 401 → `/register`). No test tooling.

### 2.4 Tests (`backend/tests/`)

12 files, 88 test functions → **109 collected** (parametrization). Fully offline:
agents are `ScriptedAgentAdapter` or `httpx.MockTransport`; every LLM path runs
`LLMService(api_key="")` (heuristic mode). `pytest.ini`: `asyncio_mode=auto`,
`integration` marker registered.

### 2.5 CI (`.github/workflows/`)

`ci.yml` (backend pytest + frontend build), `lint.yml` (ruff), `security.yml`
(Gitleaks + pip-audit, weekly). No integration-test separation, no type-check job.

## 3. API contracts that must not break

1. All existing routes under `/api/*` (auth, agents, scenarios, test-runs,
   sessions, traces, reports, darwin, playground WS) — payloads in
   `docs/api-reference.md` and mirrored in `frontend/src/lib/types.ts`.
2. Agent contract: `POST {agent}/conversation` with
   `{session_id, message, metadata}` → `{reply, tool_calls, state, timings,
   error, interrupted}`.
3. Score semantics: T/Q/R/L/E weights (0.30/0.25/0.20/0.15/0.10), fitness =
   `1 - overall/100` (higher fitness = worse agent behavior).
4. Darwin budget cap: `population × generations ≤ 60` (API clamp
   `api/darwin.py:67-71` + engine clamp `darwin/evolution.py:43,89-90`).
5. Registration auto-provisions the two demo agents (auth.py:23-39).

## 4. Known limitations & risks (pre-integration)

| # | Finding | Risk class |
|---|---|---|
| L1 | No server-side audio/STT path at all; `send_audio` raises `NotImplementedError` | The gap VoxLab 2.0 closes |
| L2 | `arq` missing from `requirements.txt` while `workers/runner.py:28-29` imports it when `REDIS_URL` set | Latent broken import |
| L3 | Demo account accepts `demo123` **or** `demo1234` bypassing hash verify (`auth.py:51-53`) | Demo convenience, flag in security review |
| L4 | Budget cap 60 duplicated in two places (API + engine) — can drift | Duplication |
| L5 | T/Q/R/L/E weights duplicated in `fitness.py`, `patcher.py`, `reports.py` | Duplication |
| L6 | `Patcher.verify_patch` only effective against agents honoring `metadata.failure_config` (dictation-agent does; customer-support does not) | Behavioral asymmetry |
| L7 | In-memory rate limiter + in-process task registry: no multi-worker support | Scalability (documented) |
| L8 | No Alembic; schema via `create_all` — new models need migrations strategy for existing DBs | Migration risk for 2.0 models |
| L9 | WS playground token in query string (access logs) | Hardening item |
| L10 | Docs duplication (`API.md` vs `api-reference.md`, `DARWIN_ENGINE.md` vs `darwin-engine.md`, …) | Hygiene |
| L11 | `frontend/.env.example` says port 8001, compose uses 8000 | Confusion risk |
| L12 | Playground events mark traces `"illustrative": true` — timing data is not real audio pipeline timing | Honesty marker, must be replaced by real STT timings in 2.0 |

## 5. Dependency snapshot (baseline)

`backend/requirements.txt`: fastapi, uvicorn[standard], sqlalchemy[asyncio],
aiosqlite, asyncpg, pydantic, pydantic-settings, email-validator, PyJWT, httpx,
openai, cryptography, redis, websockets, pytest, pytest-asyncio.
**No numpy, no audio libraries** — the 2.0 audio stack is entirely additive.

## 6. Backward-compatibility commitments for VoxLab 2.0

1. Existing `/api/*` routes, schemas, and the agent conversation contract stay
   byte-compatible; new capabilities ship under `/api/v1/*`.
2. Existing 109-test suite must keep passing unchanged.
3. Darwin text-mode evolution remains the default; audio evolution is an
   additional mode.
4. The platform keeps working with **no** speech engine installed (engines are
   discovered lazily; registry reports availability honestly).
5. No new mandatory network dependency: the Whisper engine runs fully local/offline.
