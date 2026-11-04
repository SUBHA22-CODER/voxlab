# AGENTS.md — Development Guide for AI Coding Agents & Engineers

## 1. Project Overview
**VoxLab** is a specialized voice agent reliability, evolutionary fuzzing ("Darwin"), and CI crash-test platform tailored for voice dictation systems (Wispr Flow) and conversational voice agents.

---

## 2. Repository Folder Structure
```
wisprflow/
├── backend/                      # FastAPI Python Application
│   ├── app/
│   │   ├── api/                  # REST endpoints (auth, darwin, agents, scenarios)
│   │   ├── core/                 # Database engine, config, security, rate-limiting
│   │   ├── darwin/               # Evolution engine, personas, minimizer, diagnoser, patcher
│   │   ├── models/               # SQLAlchemy ORM models (User, Agent, DarwinRun, etc.)
│   │   └── services/             # LLMService, scenario runner, trace collector
│   └── tests/                    # Pytest unit & integration test suite (106 tests)
├── frontend/                     # Next.js 16 Web Application
│   └── src/
│       ├── app/                  # App router pages (dashboard, darwin, playground, register)
│       ├── components/           # UI components, brand marks, and report views
│       └── lib/                  # Auth context, API client, types
├── agent-examples/
│   ├── customer-support-agent/   # Standalone demo voice agent (Port 8100)
│   └── dictation-agent/          # Wispr Flow dictation pipeline cleaner agent (Port 8200)
├── scenarios/                    # Builtin and regression test scenarios
├── docs/                         # Full project documentation specifications
└── docker-compose.yml            # Multi-container orchestration specification
```

---

## 3. Setup & Run Commands

### 3.1 Backend Setup
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows: .venv\Scripts\activate, Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8001
```

### 3.2 Demo Agents Setup
```bash
# Terminal 2: Customer Support Agent
cd agent-examples/customer-support-agent
python -m uvicorn main:app --port 8100

# Terminal 3: Wispr Flow Dictation Agent
cd agent-examples/dictation-agent
python -m uvicorn main:app --port 8200
```

### 3.3 Frontend Setup
```bash
cd frontend
npm install
npm run dev                       # Runs Next.js dev server on http://localhost:3000
```

---

## 4. Coding Conventions & Requirements
- **Python / Backend:**
  - Follow PEP 8 with Ruff.
  - Asynchronous first: all I/O, database access, and HTTP calls MUST use `async`/`await`.
  - Type annotations: Strict typing on all API signatures and dataclasses.
  - SQLAlchemy transactions: NEVER hold open a database write transaction across HTTP network calls. Commit DB rows in isolated atomic operations.
- **Frontend / Next.js:**
  - Strict TypeScript with zero `any` declarations.
  - Styling: Vanilla CSS and Tailwind CSS design tokens. No ad-hoc inline styles.
  - Interactive elements: Always provide unique IDs and accessible labels.

---

## 5. Testing Requirements
- Every new persona or engine feature must have unit tests in `backend/tests/`.
- All tests must pass before committing:
  ```bash
  cd backend
  pytest -q
  ```
- Frontend production build must compile cleanly without errors:
  ```bash
  cd frontend
  npm run build
  ```

---

## 6. The "Never Do" List
- **NEVER** hold an open SQLite write transaction while making external HTTP or LLM requests (causes `database is locked` deadlocks).
- **NEVER** hardcode real API keys or secrets in source code. Use environment variables.
- **NEVER** bypass the hard budget cap of 60 sessions (`DARWIN_MAX_SESSIONS`) in evolution loops.
- **NEVER** introduce external cloud dependencies for basic functionality; always preserve deterministic heuristic fallbacks.
- **NEVER** separate the login flow onto an un-styled page; all auth must remain on the unified animated `/register` page.
