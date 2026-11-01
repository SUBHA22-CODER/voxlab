# VoxLab — Full P0 MVP Build Plan

Build the complete VoxLab platform in the empty `wisprflow/` workspace per the pasted spec, with the agreed decisions: **Full P0 MVP**, **hybrid infra** (SQLite + in-process workers by default; Docker Postgres/Redis provided), **OpenAI-compatible LLM client** (any provider via env vars), **browser Web Speech API** for voice.

## Repository layout
```
wisprflow/
├── frontend/            # Next.js (App Router) + TypeScript + Tailwind + shadcn/ui + Recharts
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/         # auth, agents, scenarios, test_runs, sessions, traces, reports, playground(ws)
│   │   ├── core/        # config.py, security.py (JWT + Fernet credential encryption), database.py
│   │   ├── adapters/    # base.py (VoiceAgentAdapter), http_adapter.py, websocket_adapter.py
│   │   ├── engine/      # orchestrator.py, scenario_runner.py, trace_collector.py, evaluation_engine.py, reports.py
│   │   ├── models/  schemas/  services/ (llm.py OpenAI-compatible client)  workers/
│   │   └── seed.py      # demo user, demo agent registration, scenario loading, sample run
│   ├── tests/           # pytest: adapter, runner, evaluation, scoring
│   ├── requirements.txt  Dockerfile  .env.example
├── agent-examples/customer-support-agent/   # standalone FastAPI demo agent (mock order API, tools, failure_config.json)
├── scenarios/           # 8 JSON scenarios: interruption, hinglish, context-retention, ambiguity, api-failure, silence, long-conversation, recovery
├── docs/                # architecture.md, api-reference.md, evaluation-methodology.md
├── docker-compose.yml   # postgres + redis + backend + frontend (optional profile)
└── README.md  .gitignore
```
Also `git init` in `wisprflow/` (this supersedes the stray home-dir repo for all files here).

## Backend (FastAPI)
- **DB**: SQLAlchemy 2.0 async; `DATABASE_URL` chooses `aiosqlite` (default) or `asyncpg`. Tables per spec §4: users, agents, scenarios, test_runs, sessions, events, traces, evaluations, reports. JSON columns via SQLAlchemy JSON (works on both). `create_all()` + seed on startup (Alembic deferred — noted in docs).
- **Auth**: JWT bearer, bcrypt hashing; register/login/me.
- **Agent Registry**: CRUD + connection test; credentials encrypted with Fernet; SSRF guard on endpoints (localhost allowed via dev flag so the demo agent works).
- **Adapters**: `VoiceAgentAdapter` interface per spec (`connect / send_audio / send_message / receive_events / disconnect`); HTTP adapter posts a documented standard contract `{session_id, message, context, metadata} → {reply, tool_calls, state}`; WebSocket adapter implemented for streaming agents.
- **Standard event format**: session_started, audio_received, stt_completed, user_message, llm_first_token, tool_call_started/completed, agent_message, tts_completed, interruption, error, session_ended — each with trace_id, timestamps, durations.
- **Scenario Engine**: JSON format per spec (steps: user_message / interrupt / tool_failure / silence / expect_tool / expect_state; expected_behavior; deterministic checks). Runner executes scripted text conversations through the adapter, injecting failure flags via metadata.
- **Orchestrator/Workers**: `POST /api/test-runs` creates a queued run, executes in-process asyncio worker (sequential sessions, live status polling); module structured so ARQ+Redis can be swapped in under Docker.
- **Evaluation Engine**: deterministic checks (tool called, latency budget, state, completion) + LLM judge (relevance, context retention, instruction following, naturalness — structured JSON prompt via OpenAI-compatible client; heuristic fallback + "heuristic" flag when no key) + audio checks where transcripts exist. Scoring: `0.30·T + 0.25·Q + 0.20·R + 0.15·L + 0.10·E`, configurable weights, methodology surfaced in every report. Run-vs-run comparison endpoint.
- **API surface**: spec §5 endpoints + auth + `GET /api/test-runs/{id}/report`, `GET /api/reports/{id}/compare/{other}`, `WS /ws/playground/{agent_id}`.

## Demo customer-support agent
Standalone FastAPI app speaking the VoxLab contract: product FAQ, mock order DB, tools (check_order_status, cancel_order, escalate_to_human); LLM-backed with scripted fallback. `failure_config.json` deliberately introduces failures (ignores interruptions, crashes on API 500, forgets context) so the demo can show **fail → fix config → rerun → improve**. Mock order API has a toggleable 500 mode driven by the api-failure scenario.

## Frontend (dark developer-tool aesthetic, shadcn/ui + Recharts)
Pages: /login, /register, /dashboard (stat cards + recent runs), /agents, /agents/new, /playground, /scenarios, /runs, /runs/[id], /traces/[id], /reports/[id].
- **Playground** (flagship): Text / Voice / Simulation modes; live transcripts, per-turn latency chips, event ticker, session history, replay. Voice = browser mic → Web Speech API STT → adapter → speech synthesis playback.
- **Trace viewer**: pipeline stage timeline with per-stage durations, event payload inspector, failure highlighting.
- **Reports**: weighted score breakdown, per-scenario results, methodology, before/after comparison.

## Build order (execution phases)
1. Scaffold repo + docs + docker-compose + env examples
2. Backend foundation (config, models, auth, seed)
3. Registry + HTTP/WS adapters
4. Demo agent
5. Scenario engine + orchestrator + trace collection
6. Evaluation + reports + comparison
7. Frontend scaffold + auth + dashboard
8. Agents / scenarios / runs / traces / reports pages
9. Playground (text → voice)
10. Seed demo data, end-to-end verification, polish

## Verification
- pytest covers adapters, scenario runner, evaluation, scoring math (mock LLM).
- Live check: run demo agent + backend, execute a full benchmark via API, confirm trace + report + deliberate failure detected.
- Frontend: production build passes; README documents `uvicorn` + `npm run dev` quickstart and the `docker compose --profile full up` path.

## Notes
- Ports: backend 8000, frontend 3000, demo agent 8100.
- Audio-noise/accent scenarios stay text-declared but deferred (need real audio), per spec.
- Public deployment is out of scope for this session; local MVP + deploy-ready Docker is the deliverable.