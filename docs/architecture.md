# VoxLab Architecture

VoxLab is the testing, debugging and reliability infrastructure for voice AI
agents. Developers register an existing agent, run stress scenarios against it,
inspect full pipeline traces, and receive a transparent benchmark report.

```
┌────────────────────┐        ┌─────────────────────────────────────────┐
│  Next.js Frontend  │  HTTP  │            FastAPI Backend              │
│  (dashboard,       │◄──────►│  ┌───────────┐   ┌────────────────────┐ │
│   playground,      │   WS   │  │ API layer │──►│ Orchestrator       │ │
│   traces, reports) │        │  └───────────┘   │ (in-process worker │ │
└────────────────────┘        │                  │  or ARQ via Redis) │ │
                              │  ┌───────────┐   └─────────┬──────────┘ │
┌────────────────────┐        │  │ Scenario  │   ┌─────────▼──────────┐ │
│  External Voice    │◄───────┤  │ Engine    │   │ Scenario Runner    │ │
│  Agent (HTTP/WS)   │ adapter│  └───────────┘   │ (per-session)      │ │
│  e.g. demo agent   │        │                  └─────────┬──────────┘ │
└────────────────────┘        │  ┌───────────────────┐     │ events     │
                              │  │ Evaluation Engine │◄────┤ + traces   │
                              │  │ deterministic +   │     ▼            │
                              │  │ LLM judge /       │  PostgreSQL or   │
                              │  │ heuristic fallback│  SQLite          │
                              │  └───────────────────┘                  │
                              └─────────────────────────────────────────┘
```

## Modules (spec §1)

| Module | Where | Responsibility |
|---|---|---|
| Agent Registry | `backend/app/api/agents.py`, `models` | Register agents, encrypted credentials, SSRF-guarded endpoints, connection testing |
| Voice Playground | `backend/app/api/playground.py`, `frontend/.../playground` | Live conversations over WebSocket; text and voice (browser Web Speech API) modes |
| Scenario Engine | `backend/app/engine/scenario_runner.py` | Execute scripted scenario steps (messages, interrupts, tool-failure injection, silence) through adapters |
| Observability | `backend/app/engine/trace_collector.py` | Standard event format + per-turn pipeline stage timings, persisted as events + traces |
| Evaluation Engine | `backend/app/engine/evaluation_engine.py` | Deterministic checks, LLM judge (heuristic fallback), scoring |
| Reports | `backend/app/engine/reports.py` | Transparent weighted benchmark score, failure diagnosis, run comparison |

## Adapter layer

`app/adapters/base.py` defines the standard `VoiceAgentAdapter` interface
(`connect`, `send_message`, `send_audio`, `disconnect`). Every external agent
framework plugs in through one of:

- **HTTP adapter** — request/response contract (see [api-reference.md](api-reference.md))
- **WebSocket adapter** — streaming JSON frames

Adapters normalize provider-specific responses into `AgentTurnResult`
(reply, tool_calls, state, timings, error). This is what makes VoxLab
extensible without asking developers to rebuild their agents.

## Event flow in a benchmark run

1. `POST /api/test-runs` validates the request, creates a queued run row.
2. The orchestrator dispatches an in-process asyncio task (or enqueues to
   Redis/ARQ when `REDIS_URL` is configured).
3. Per scenario: a `Session` row is created with a fresh trace id; the runner
   executes steps through the adapter while the `TraceCollector` records
   events (user_message, agent_processing, tool_call, agent_message,
   interruption, error, …) and per-turn pipeline stage durations.
4. The evaluation engine scores the session (deterministic checks + judge).
5. After all sessions, a report is generated and the run is marked completed.

Runs are isolated per session; a failing agent cannot poison other sessions.

## Data model (PostgreSQL / SQLite)

users → agents → test_runs → sessions → events / traces / evaluations,
plus scenarios and reports. JSON columns hold scenario definitions, event
payloads, trace stage data, evaluation scores and report summaries. Large
audio artifacts are intentionally out of the database (the MVP stores
transcripts, not audio blobs).

## Hybrid infrastructure

- **Default (zero-install)**: SQLite + in-process asyncio workers.
- **Production path**: `docker compose --profile full up` brings up
  PostgreSQL, Redis, backend, frontend and the demo agent. `DATABASE_URL`
  switches the SQLAlchemy engine; `REDIS_URL` switches run dispatch to ARQ.

## Deliberate design decisions

- **Scripted-first scenarios** before real audio (per spec §3): text scenarios
  run deterministically and offline; audio scenarios are declared in the
  format but marked deferred until recorded/generated inputs land.
- **LLM judge is pluggable**: any OpenAI-compatible endpoint works; when no
  key is configured the platform degrades to transparent heuristics and labels
  the report `judge_mode: heuristic` instead of pretending.
- **Failure switches, not failure code**: the demo agent's bugs are config
  (`failure_config.json`), so "break → fix → rerun → improve" is a config
  change, showing score movement credibly.
