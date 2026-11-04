# VoxLab End-to-End Functional Test Report

**Target Scope:** Complete user journey across Agent Registry, Voice Playground, Scenario Engine, Evaluation Engine, Observability, and Benchmark Reports.  
**Result Summary:** 6/6 Functional Workflows PASSED.

---

## 1. Journey 1: Agent Registry & Secret Protection
* **Test Sequence:**
  1. POST `/api/agents` with authentication credentials (`api_key`).
  2. GET `/api/agents/{id}` and confirm plaintext key is omitted from response schema.
  3. POST `/api/agents/{id}/connect` to test active reachability.
  4. POST `/api/agents` with invalid/unreachable URL and verify graceful unreachable state (`ok: false, reachable: false`).
  5. PATCH `/api/agents/{id}` and DELETE `/api/agents/{id}`.
* **Findings:**
  - Credentials encrypted using Fernet symmetric cryptography in `voxlab.db`.
  - Endpoint guard correctly validated schemes (`http`, `https`, `ws`, `wss`).
  - Cross-user isolation verified: secondary tenant receives HTTP 404 when querying an agent owned by another user.
* **Status:** **PASS**

---

## 2. Journey 2: Voice Playground & Realtime Streaming
* **Test Sequence:**
  1. Connect WebSocket to `/ws/playground/{agent_id}?token={jwt}`.
  2. Send text frames and Web Speech simulated audio frames.
  3. Verify `session_started`, `agent_message`, and `session_ended` protocol frames.
  4. Verify waterfall stage latency measurements (`agent_processing`, `tool_execution`, `e2e`).
* **Findings:**
  - Turn events stream in realtime with strictly monotonic sequence numbers (`0, 1, 2...`).
  - Fixed duplicate event emission in database by properly tracking flushed events slice (`collector._events[flushed_through:]`).
* **Status:** **PASS**

---

## 3. Journey 3: Scenario Engine & Runner
* **Test Sequence:**
  1. Builtin scenarios loaded from `scenarios/*.json` on startup (11 scenarios).
  2. Custom multi-turn scenario created with explicit checks (`reply_contains`, `reply_nonempty`).
  3. Scenario runner executed step sequence against live demo agent.
  4. Verified injected interruptions (`interrupt: true`) and tool failures (`inject: {"tool_failure": true}`).
* **Findings:**
  - Multi-turn state transitions (`SessionState.turns`, `order_id`, `cancelled`) persisted correctly across turns.
  - Context retention validated over 6+ turn conversations.
* **Status:** **PASS**

---

## 4. Journey 4: Evaluation Engine
* **Test Sequence:**
  1. Deterministic checks evaluated across task completion, reply contents, and tool invocations.
  2. Latency scored against budget using inverse ratio formula: $\text{score} = \min(100, 100 \times \text{budget} / \text{actual})$.
  3. Quality and context retention evaluated in both LLM judge mode and deterministic heuristic mode.
* **Findings:**
  - Scores adhere strictly to $[0, 100]$ bounds.
  - Heuristic mode correctly sets `judge_mode: "heuristic"` in evaluation feedback, guaranteeing no fabricated or simulated judge output.
* **Status:** **PASS**

---

## 5. Journey 5: Observability & Tracing
* **Test Sequence:**
  1. GET `/api/sessions/{id}` and GET `/api/sessions/{id}/traces`.
  2. Direct trace retrieval via GET `/api/traces/{trace_id}`.
  3. Verify event stream ordering, duration measurements, and stage breakdowns.
* **Findings:**
  - Trace collector correctly breaks down end-to-end latency into component timings: `llm_ms`, `tool_ms`, and network overhead.
  - Monotonicity verified across all generated events.
* **Status:** **PASS**

---

## 6. Journey 6: Benchmark Reports
* **Test Sequence:**
  1. Executed test run with multiple scenarios.
  2. Generated transparent weighted benchmark report.
  3. Verified report formula:
     $$\text{Score} = 0.30T + 0.25Q + 0.20R + 0.15L + 0.10E$$
  4. Exported report JSON via `/api/reports/{id}/export`.
  5. Ran second benchmark run and executed comparison endpoint `/api/reports/{id}/compare/{id2}`.
* **Findings:**
  - Summary score accurately matches the weighted sum within $\pm 0.01$ rounding tolerance.
  - Comparison deltas clearly report component-level gains and regressions.
* **Status:** **PASS**

