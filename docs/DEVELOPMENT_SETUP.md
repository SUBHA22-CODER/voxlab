# VoxLab Local Development & Setup Guide

This guide walks through configuring, installing, and running VoxLab and its Darwin evolutionary fuzzing engine locally.

---

## 1. Prerequisites

- **Python 3.11+**
- **Node.js 18+ or 20+** (with npm)
- **Git**

---

## 2. Clone the Repository

```bash
git clone https://github.com/SUBHA22-CODER/voxlab.git
cd voxlab
```

---

## 3. Backend Setup (FastAPI)

```bash
cd backend
python -m venv .venv

# Activate Virtual Environment:
# On Windows:
.venv\Scripts\activate
# On macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```
- API Base: `http://localhost:8001`
- Swagger UI: `http://localhost:8001/docs`

---

## 4. Standalone Demo Voice Agents

Open two additional terminals to run the demo test agents:

```bash
# Terminal 2: Customer Support Demo Agent
cd agent-examples/customer-support-agent
python -m uvicorn main:app --port 8100

# Terminal 3: Wispr Flow Dictation Agent
cd agent-examples/dictation-agent
python -m uvicorn main:app --port 8200
```

---

## 5. Frontend Setup (Next.js 16)

In a fourth terminal:

```bash
cd frontend
npm install
npm run dev
```
- Open [http://localhost:3000](http://localhost:3000)
- Click **"Explore with Demo Account"** (or login with `demo@voxlab.dev` / `demo123`)

---

## 6. Running Automated Tests

```bash
# Run Backend Test Suite (109 tests)
cd backend
pytest -v

# Run Frontend Production Build Check
cd frontend
npm run build
```

