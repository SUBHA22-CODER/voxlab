# VoxLab — Voice AI Crash-Test Lab & Darwin Evolutionary Fuzzer

[![Tests](https://img.shields.io/badge/pytest-106%20passed-emerald)](https://github.com)
[![Next.js](https://img.shields.io/badge/Next.js-16.4.3-black)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-teal)](https://fastapi.tiangolo.com)
[![Wispr Flow](https://img.shields.io/badge/Tailored%20for-Wispr%20Flow-6366f1)](https://wisprflow.ai)

**VoxLab** is an automated reliability, fuzzing, and CI testing platform for conversational voice AI agents and speech-to-text dictation pipelines (such as Wispr Flow). It acts as a crash-test dummy: mutating speech personas, injecting hostile edge cases (interruptions, self-corrections, filler words, command confusion), delta-debugging failures down to 1-turn minimal reproductions, and automatically verifying code fixes in a sandbox.

---

## ⚡ Key Capabilities

- **🧬 Darwin Evolutionary Fuzzing:** Multi-generation genetic fuzzer tailored for voice agents and dictation pipelines.
- **🎯 Wispr Flow Attack Personas:**
  - *Self-Corrector:* Tests mid-sentence intent changes ("send Tuesday, no wait, Wednesday").
  - *Filler-Heavy Rambler:* Tests disfluency cleanup without semantic loss.
  - *Command-vs-Dictation Confuser:* Disambiguates spoken commands ("period", "new line") from literal text.
  - *Jargon & Names Speaker:* Evaluates phonetic transcription of code symbols, acronyms, and proper nouns.
  - *Impatient Interrupter:* Tests audio barge-ins and state rollback.
- **🔍 Delta Debugging (`ddmin`):** Automatically isolates multi-turn conversation crashes to a 1-turn or 2-turn minimal repro sequence.
- **🩺 AI Root-Cause Diagnostic & Auto-Doctor:** Classifies failure taxonomy and generates verified git diff patches tested in a sandbox.
- **📦 1-Click CI Regression Suite Export:** Exports discovered bugs into standard JSON scenarios for automated CI gates.
- **📊 Real-Time Turn Tracing & Live Charting:** Turn-level STT, LLM, tool, and TTS latency breakdowns.

---

## 🚀 Quick Start (Local Setup)

### 1. Backend Server (Port 8001)
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8001
```

### 2. Demo Voice Agents
```bash
# Terminal 2: Customer Support Agent (Port 8100)
cd agent-examples/customer-support-agent
python -m uvicorn main:app --port 8100

# Terminal 3: Wispr Flow Dictation Agent (Port 8200)
cd agent-examples/dictation-agent
python -m uvicorn main:app --port 8200
```

### 3. Frontend Web Application (Port 3000)
```bash
cd frontend
npm install
npm run dev
```
Open **[http://localhost:3000/register](http://localhost:3000/register)** to begin fuzzing and benchmarking.

---

## 🐳 Docker Compose (1-Command Deployment)
```bash
cp .env.example .env
docker compose --profile full up -d --build
```

---

## 📚 Documentation
Comprehensive documentation is available in the [`docs/`](./docs) folder:
- [PRD.md](./docs/PRD.md) — Product requirements and MVP specifications
- [ARCHITECTURE.md](./docs/ARCHITECTURE.md) — High-level architecture and system components
- [AGENT_DESIGN.md](./docs/AGENT_DESIGN.md) — Attack personas, failure taxonomies, and handoff rules
- [DATA_MODEL.md](./docs/DATA_MODEL.md) — Database models and schema tables
- [API.md](./docs/API.md) — REST API endpoints and payload specifications
- [TASKS.md](./docs/TASKS.md) — Completed implementation roadmap
- [EVALS.md](./docs/EVALS.md) — 10 concrete evaluation test cases and scoring metrics
- [DEPLOYMENT.md](./docs/DEPLOYMENT.md) — Docker and cloud deployment guide
- [TESTING.md](./docs/TESTING.md) — Test suite execution guide (106 tests)
- [SECURITY.md](./docs/SECURITY.md) — Credential encryption, SSRF protection, and JWT security
- [DECISIONS.md](./docs/DECISIONS.md) — Architecture decision records (ADRs)
