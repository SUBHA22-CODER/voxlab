# VoxLab — The Voice AI Crash-Test Lab

**Build voice agents. Break them. Benchmark them. Make them production-ready.**

VoxLab is developer infrastructure for voice-agent reliability: connect your
existing voice agent, run realistic stress scenarios (interruptions, API
failures, Hinglish, memory probes), inspect every pipeline event, and get a
transparent benchmark report with failure diagnosis.

```
Register agent → Run scenarios → Every turn traced → Scored report → Fix → Rerun → Compare
```

## The demo story (two minutes)

1. Start the demo agent (ships deliberately broken — `failure_config.json`):
   ```bash
   cd agent-examples/customer-support-agent
   uvicorn main:app --port 8100
   ```
2. Start VoxLab, open the dashboard, run the built-in benchmark against the
   **Customer Support Agent (Demo)** — it scores **~66/100** with 6 of 8
   scenarios failing, each failure traced to the exact turn.
3. Fix the agent (flip the switches):
   ```bash
   curl -X POST http://localhost:8100/admin/failure-config \
        -H "Content-Type: application/json" \
        -d '{"ignore_interruptions": false, "crash_on_tool_error": false, "forget_context": false, "hinglish_support": true}'
   ```
4. Rerun the same benchmark → **~95/100**, and use **Compare** on the report
   to see the before/after deltas per component.

## Quickstart (zero-install)

Requires Python 3.11+ and Node 20+.

```bash
# 1. Backend
cd backend
python -m venv .venv && .venv\Scripts\activate      # Windows (Git Bash: source .venv/Scripts/activate)
pip install -r requirements.txt
uvicorn app.main:app --port 8001                     # uses SQLite + in-process workers

# 2. Seed demo data (demo user, demo agent, 8 builtin scenarios)
python -m app.seed

# 3. Frontend (new terminal)
cd ../frontend
npm install
cp .env.example .env.local                           # NEXT_PUBLIC_API_URL=http://localhost:8001
npm run dev                                          # http://localhost:3000
```

Sign in at http://localhost:3000 with **demo@voxlab.dev / demo1234**.

Optional: `python -m app.seed --with-run` also executes a full benchmark if
the demo agent is running on :8100.

## Docker (production path)

```bash
cp .env.example .env    # set SECRET_KEY, ENCRYPTION_KEY, LLM_API_KEY…
docker compose --profile full up --build
```

Brings up PostgreSQL, Redis, backend, frontend and the demo agent. The
backend switches to Postgres via `DATABASE_URL`; run dispatch switches to
Redis/ARQ via `REDIS_URL`.

## LLM configuration (any provider)

The LLM judge and the demo agent's LLM mode use an OpenAI-compatible client:

```env
LLM_API_KEY=...                  # omit → transparent heuristic scoring
LLM_BASE_URL=https://api.openai.com/v1    # or Z.ai / Groq / DeepSeek / Ollama
LLM_MODEL=gpt-4o-mini
```

Reports label which mode ran: `judge_mode: llm` or `heuristic`.

## Repository layout

```
frontend/                            Next.js 16 · App Router · Tailwind · Recharts
  src/app/(app)/dashboard            overview + recent runs
  src/app/(app)/playground           live text/voice conversations (Web Speech API)
  src/app/(app)/agents|scenarios|runs|traces|reports
backend/                             FastAPI · SQLAlchemy async · SQLite/Postgres
  app/api/                           REST + WebSocket routers
  app/adapters/                      VoiceAgentAdapter: HTTP + WebSocket
  app/engine/                        scenario runner, tracing, evaluation, reports, orchestrator
  app/core/                          config, security (JWT + Fernet), rate limit, DB
  tests/                             91 pytest tests (unit + integration + e2e)
  scripts/live_e2e.py                14-check live verification against running servers
agent-examples/customer-support-agent/   demo agent with failure switches
scenarios/                           8 builtin scenario definitions
docs/                                architecture · api-reference · evaluation-methodology
```

## Scenario library

Interruption · Context retention · API failure (graceful handling) · Hinglish
understanding · Ambiguous request · Unexpected silence · Long-conversation
memory · Recovery after failure. Each ships with deterministic checks and an
expected-behavior description; see [docs/evaluation-methodology.md](docs/evaluation-methodology.md)
for the scoring math.

## Verification

```bash
cd backend && python -m pytest            # 91 tests
./scripts/live_e2e.py                     # 14 end-to-end checks (needs both servers + demo agent)
cd ../frontend && npm run build           # production build
```

## Security notes

- Agent credentials are encrypted at rest (Fernet); never returned by the API.
- Agent endpoints pass an SSRF guard (`ALLOW_LOCAL_ENDPOINTS=false` in
  production to block private/loopback targets).
- JWT bearer auth, bcrypt-class password hashing (PBKDF2-SHA256), rate-limited
  auth endpoints, generic 5xx responses with server-side logging.
- **Known MVP tradeoffs** (fine for local demos, address before public
  deployment): JWT lives in localStorage (React-escaped rendering, no raw
  HTML anywhere — the standard cookie hardening is the next step), the demo
  agent's `/admin/*` endpoints are unauthenticated (localhost demo only —
  never expose :8100), no per-user quota beyond auth rate limiting, and
  trace transcripts are not yet PII-redacted.

## Docs

- [docs/architecture.md](docs/architecture.md) — modules, adapter layer, event flow
- [docs/api-reference.md](docs/api-reference.md) — endpoints + agent contract + WS protocol
- [docs/evaluation-methodology.md](docs/evaluation-methodology.md) — how scores are computed

---

VoxLab is the testing, debugging and reliability infrastructure for the next
generation of voice AI agents.
