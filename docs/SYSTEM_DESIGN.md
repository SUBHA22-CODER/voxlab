# VoxLab System Design

## Architecture Overview

VoxLab comprises three primary systems:
1. **Control Plane & Web UI (Next.js 16 + Tailwind CSS):** Real-time interactive playground, Darwin evolutionary campaign visualizer, trace timeline inspection, and benchmark dashboards.
2. **API & Orchestration Engine (FastAPI + Async SQLAlchemy):** Scenario execution engine, trace event stream collector, deterministic & LLM evaluation evaluators, and JWT project isolation.
3. **Darwin Evolutionary Fuzzing Engine:** In-process genetic algorithm worker, mutation engine, Delta Debugging minimizer, and root-cause diagnoser.

```mermaid
flowchart TD
    UI["Frontend Next.js (Port 3000)"] <-->|REST & WebSocket| API["Backend FastAPI (Port 8001)"]
    API <-->|Async Engine| DB[("SQLite Database voxlab.db")]
    
    subgraph Execution Pipeline
        SR["Scenario Runner"] -->|HTTP / WS Stream| AGENT["Target Voice Agent (e.g. Port 8100/8200)"]
        SR -->|Event Collector| TR["Trace & Event Collector"]
        TR --> EVAL["Evaluation Engine (T, Q, R, L, E)"]
    end

    subgraph Darwin Engine
        DE["Evolution Loop"] -->|Generate Population| GEN["Genome Mutator"]
        GEN --> SR
        EVAL -->|Fitness Calculation| FIT["Fitness Evaluator"]
        FIT -->|Score < Threshold| DD["Delta Debugging (ddmin)"]
        DD --> DIAG["Root Cause Diagnoser"]
        DIAG --> REG["Regression Scenario Exporter"]
    end

    API --> Execution Pipeline
```

---

## Concurrency & Safety Controls

1. **Database Session Isolation:**
   - FastAPI dependency `get_db` opens and closes scoped async sessions per request.
   - **Critical Rule:** Database write transactions are never held across external HTTP or WebSocket calls, preventing SQLite lock contention.

2. **Darwin Session Budget Cap:**
   - Every Darwin run strictly caps total executed sessions:
     $$\text{Budget} = \text{population\_size} \times \text{generations} \le 60$$
   - This prevents infinite loops, memory leaks, and runaway API costs.

3. **In-Process Task Dispatch:**
   - Long-running Darwin runs are dispatched to an async worker queue in `backend/app/darwin/evolution.py`, allowing client requests to poll progress or cancel anytime via `POST /api/darwin/runs/{id}/cancel`.

