# System Architecture: VoxLab & Darwin Engine

> **Assumptions:**
> - Backend runs FastAPI (asynchronous Python 3.11) with SQLAlchemy 2.0 (aiosqlite / asyncpg).
> - Frontend is Next.js 16 (React 19, Turbopack, Tailwind CSS, Recharts).
> - Target agents communicate via standardized HTTP JSON schemas (`/conversation`).

---

## 1. High-Level Architecture Diagram

```
+--------------------------------------------------------------------------+
|                       Next.js Frontend (Port 3000)                       |
|  - Darwin Dashboard & Charting (Recharts)   - Trace Explorer             |
|  - Interactive Voice Playground             - Benchmark Test Runner      |
+------------------------------------+-------------------------------------+
                                     |  HTTP REST / WebSocket
                                     v
+--------------------------------------------------------------------------+
|                        FastAPI Backend (Port 8001)                       |
|  +--------------------+  +----------------------+  +------------------+  |
|  | Darwin Evolution   |  | Failure Minimizer    |  | Auto-Doctor      |  |
|  | - Population Gen   |  | - ddmin Algorithm    |  | - Diagnoser      |  |
|  | - Mutator / Fuzzer |  | - Minimal Repro Extr |  | - Sandbox Verify |  |
|  +---------+----------+  +----------+-----------+  +--------+---------+  |
|            |                        |                       |            |
|            +-------------------+----+-----------------------+            |
|                                |                                         |
|                                v                                         |
|            +----------------------------------------+                    |
|            | Evaluation Engine & Scorer             |                    |
|            | - Intent Fidelity & Entity Accuracy    |                    |
|            | - Cleanup Quality & Formatting Checks  |                    |
|            +-------------------+--------------------+                    |
+--------------------------------+-----------------------------------------+
                                 |
                 +---------------+---------------+
                 |                               |
                 v                               v
+----------------------------------+  +------------------------------------+
| SQLite / PostgreSQL Database     |  | Target Agent Endpoints             |
| - Users & Auth                   |  | - Wispr Dictation Agent (:8200)    |
| - Agents & Traces                |  | - Customer Support Agent (:8100)   |
| - Darwin Runs, Gens, Findings    |  | - Production Custom Webhooks       |
+----------------------------------+  +------------------------------------+
```

---

## 2. Component Breakdown

### 2.1 Darwin Evolutionary Engine (`app/darwin/evolution.py`)
- **Lifecycle:** Asynchronously orchestrated via `asyncio.create_task` with cancellation handles.
- **Genetic Pipeline:**
  1. Initialize seed population with selected adversarial personas.
  2. For each candidate: materialize utterance (LLM or heuristic) -> execute turn against agent -> evaluate output -> compute fitness.
  3. Survivors selected via truncation selection ($Top-K$).
  4. Children generated via crossover and mutation operators (`swap_persona`, `inject_interruption`, `inject_api_failure`, `extend_conversation`).
- **Database Isolation:** DB sessions are short and isolated (<5ms commit window) after HTTP calls complete, avoiding SQLite write lock contention.

### 2.2 Adaptive Attacker (`app/darwin/attacker.py`)
- Employs an LLM judge prompt conditioned on persona behavior, attack strategy, and prior conversation turns.
- Includes a 100% offline heuristic generator bank that activates when rate-limited (HTTP 429) or when operating without an API key.

### 2.3 Delta Debugging Minimizer (`app/darwin/minimizer.py`)
- Implementation of the classic `ddmin` algorithm.
- Recursively divides multi-turn conversational sequences to isolate the minimal subset of turns that reproduce the adversarial degradation score ($\ge 0.5$).

### 2.4 Auto-Doctor Patcher & Sandbox (`app/darwin/patcher.py`)
- Rule-based regex classification + LLM reasoning for root cause analysis.
- Generates unified git diffs targeting agent code switches.
- Executes sandbox re-runs to verify that the generated patch resolves the vulnerability without regressing baseline turns.
