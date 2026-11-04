# Implementation Tasks & Roadmap

> **Reference:** Cross-linked with [PRD.md](file:///c:/Users/Subha%20Prasana%20Parida/OneDrive/Desktop/wisprflow/docs/PRD.md) and [ARCHITECTURE.md](file:///c:/Users/Subha%20Prasana%20Parida/OneDrive/Desktop/wisprflow/docs/ARCHITECTURE.md).

---

## Phase 1: Environment & Foundation Setup
- [x] **Task 1.1: Core FastAPI Backend & Async SQLite**
  - *Acceptance Criteria:* FastAPI application starts on port 8001; SQLAlchemy initializes tables with SQLite WAL mode and 60s busy timeout.
- [x] **Task 1.2: Next.js Frontend Initialization**
  - *Acceptance Criteria:* Next.js 16 App Router application compiles cleanly with Tailwind CSS and brand equalizer aesthetics.
- [x] **Task 1.3: Unified Authentication Flow**
  - *Acceptance Criteria:* Animated `/register` page supports in-page tab switching between "Create Account" and "Sign In"; automatically seeds starter agents upon registration.

---

## Phase 2: Darwin Fuzzing & Evolutionary Engine
- [x] **Task 2.1: Adversarial Personas Implementation**
  - *Acceptance Criteria:* Implemented `self_corrector`, `filler_heavy_rambler`, `command_vs_dictation_confuser`, and `jargon_and_names_speaker` in `app/darwin/personas.py`.
- [x] **Task 2.2: Genetic Operators & Genome Mutation**
  - *Acceptance Criteria:* Implemented `swap_persona`, `inject_interruption`, `inject_api_failure`, `extend_conversation`, and `crossover` in `app/darwin/genome.py`.
- [x] **Task 2.3: Adaptive Attacker with Rate-Limit Fallback**
  - *Acceptance Criteria:* LLM completion with `max_retries=1` and `timeout=10s`; instantaneous fallback to heuristic utterance bank if provider is unavailable.
- [x] **Task 2.4: Evaluation Engine & Dictation Metrics**
  - *Acceptance Criteria:* Intent fidelity, entity accuracy, cleanup quality, and command handling scoring in `app/darwin/fitness.py`.

---

## Phase 3: Failure Minimization & Auto-Doctor
- [x] **Task 3.1: Delta Debugging (`ddmin`) Implementation**
  - *Acceptance Criteria:* Multi-turn failed trajectories recursively shrink to 1-turn or 2-turn minimal repro sequences (`app/darwin/minimizer.py`).
- [x] **Task 3.2: AI Root Cause Diagnostic**
  - *Acceptance Criteria:* Rule-based pre-classification + LLM reasoning generating confidence percentage and failure taxonomy (`app/darwin/diagnoser.py`).
- [x] **Task 3.3: Sandbox Auto-Doctor Patch Verification**
  - *Acceptance Criteria:* Generates unified git diffs and runs sandbox evaluation proving vulnerability fix (`app/darwin/patcher.py`).
- [x] **Task 3.4: 1-Click Regression Suite Export**
  - *Acceptance Criteria:* Exports findings to `scenarios/regression/` with automatic startup seeding (`app/darwin/regression.py`).

---

## Phase 4: UI, Dashboard & CI Integration
- [x] **Task 4.1: Darwin Dashboard & Live Generation Charting**
  - *Acceptance Criteria:* Recharts AreaChart showing Average Population Fitness vs Peak Attack Fitness over generations (`/darwin/[id]`).
- [x] **Task 4.2: Discovered Vulnerabilities Table**
  - *Acceptance Criteria:* Displays minimized repro sequence, root cause badge, "Export to Regression", and "Verify Fix in Sandbox" buttons.
- [x] **Task 4.3: Real-Time Incremental Progress Updates**
  - *Acceptance Criteria:* Live session counters update per-candidate without waiting for entire generations to finish.

---

## Phase 5: Containerization & Production Deployment
- [x] **Task 5.1: Multi-Service Docker Compose**
  - *Acceptance Criteria:* `docker-compose.yml` orchestrates Postgres, Redis, Backend, Frontend, Customer Support Agent, and Dictation Agent.
- [x] **Task 5.2: Production Build & Security Hardening**
  - *Acceptance Criteria:* 106 pytest tests passing; Next.js production build passing; `.gitignore` protecting secrets and SQLite WAL files.
