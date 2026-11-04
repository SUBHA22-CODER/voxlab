# Product Requirements Document (PRD): VoxLab & Darwin Engine

> **Project Assumptions:**
> - **Product:** VoxLab — Voice AI Crash-Test Lab with the "Darwin" Evolutionary Fuzzing Engine.
> - **Tailoring:** Engineered specifically for voice dictation pipelines (Wispr Flow) and conversational voice agents.
> - **Operating Mode:** Zero external cloud dependencies required (heuristic fallbacks guarantee 100% offline functionality).

---

## 1. Executive Summary & Pitch
**VoxLab** is an automated reliability, fuzzing, and CI testing platform for conversational voice AI agents and voice-to-text dictation pipelines (such as Wispr Flow). It acts as a crash-test dummy: mutating speech personas, injecting hostile edge cases (interruptions, self-corrections, filler words, command confusion), delta-debugging failures down to 1-turn minimal reproductions, and automatically verifying code fixes in a sandbox.

---

## 2. Target Users & Problem Statement
1. **Speech-to-Text & Dictation Engineers (e.g., Wispr Flow):**
   - *Problem:* Real humans speak with false starts, verbal fillers ("um", "you know"), rapid self-corrections ("send Tuesday no wait Wednesday"), and ambiguous formatting commands ("period", "new line"). Traditional static test cases fail to catch combinatorial edge cases.
2. **Conversational AI Engineers:**
   - *Problem:* Voice agents break during user barge-ins, latency spikes, and Hinglish/code-switching, causing hallucinations or tool execution loops.
3. **QA & DevOps Leads:**
   - *Problem:* No automated CI gate exists to catch voice regression bugs before deploying pipeline models to production.

---

## 3. Core Features (MVP)

### 3.1 Darwin Evolutionary Fuzzing Engine
- **Genetic Population Loop:** Runs multi-generation attack evolution ($N$ generations, population $P$, elite survivor selection).
- **Targeted Adversarial Personas:**
  - `self_corrector`: Rapid mid-sentence intent changes ("meeting at 2, wait, 3, actually 4").
  - `filler_heavy_rambler`: Heavy filler injections ("um", "like", "you know", false starts).
  - `command_vs_dictation_confuser`: Literal vs structural command ambiguities ("delete that", "new line", "period").
  - `jargon_and_names_speaker`: Complex entity spelling, brand names, and code identifiers.
  - `impatient_interrupter`: Barge-ins cut off midway through agent synthesis.
  - `hinglish_code_switcher`: Hindi-English bilingual phrasing.
  - `social_engineer`: Prompt-injection and jailbreak boundary testing.

### 3.2 Delta Debugging Failure Minimizer (`ddmin`)
- Automatically shrinks failing multi-turn conversations down to the 1-turn or 2-turn minimal repro sequence while preserving the failure condition.

### 3.3 AI Root-Cause Diagnostic & Auto-Doctor
- Analyzes minimized failure traces to assign an error taxonomy (e.g. `self_correction_missed`, `filler_not_removed`, `command_misinterpreted`, `hallucination`).
- Generates precise remediation patch diffs and verifies them against the target agent in an isolated sandbox.

### 3.4 1-Click Regression Suite Export
- Discovered vulnerabilities export directly as reproducible JSON scenarios (`scenarios/regression/`) integrated into CI test runs.

### 3.5 Real-Time Interactive Playground & Benchmarking
- Manual turn-level execution with STT, LLM, TTS, and tool execution latency breakdowns.

---

## 4. Non-Functional Requirements
- **Budget Control:** Hard maximum ceiling on session executions per campaign (`DARWIN_MAX_SESSIONS=60`).
- **Resilience:** Fallback to deterministic heuristic attack patterns if LLM provider is unavailable or rate-limited.
- **Concurrency & Storage:** SQLite with WAL mode and 60s busy timeout for local dev; PostgreSQL for production.
- **Latency Budget:** Turn-level timeout capped at 15s to prevent stalled pipelines.
