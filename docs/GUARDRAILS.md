# Guardrails & Safety Architecture

> **Assumptions:**
> - Guardrails prevent Server-Side Request Forgery (SSRF), unbounded resource starvation, and prompt injection leaks.

---

## 1. Network & Endpoint Security Guardrails

### 1.1 Endpoint Guard (`app/services/endpoint_guard.py`)
- **Private IP & Loopback Filter:** Validates registered agent endpoints before requests are dispatched.
- **Production Mode:** Rejects `localhost`, `127.0.0.1`, `0.0.0.0`, and RFC 1918 private subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) when `ALLOW_LOCAL_ENDPOINTS=false`.
- **Allowed Schemes:** Strictly restricts URLs to `http://`, `https://`, `ws://`, and `wss://`.

---

## 2. Execution Budget & Resource Guardrails

### 2.1 Hard Session Ceiling (`DARWIN_MAX_SESSIONS`)
- The evolution loop enforces a hard session limit (default: 60 sessions). Once `sessions_executed >= max_budget`, evolution immediately ceases and records the final generation.

### 2.2 Turn Latency Timeout
- All HTTP requests to target agents are wrapped with a 15-second client-side timeout. Prevents hung worker threads.

### 2.3 LLM Rate-Limit Breaker
- In `app/services/llm.py`, `AsyncOpenAI` client enforces `max_retries=1` and `timeout=10.0`. If a 429 occurs, it triggers an instant circuit-break to offline heuristic generators.

---

## 3. Database Integrity & Concurrency Guardrails
- **WAL Journaling:** SQLite databases are forced into Write-Ahead Logging (`PRAGMA journal_mode=WAL`).
- **Busy Timeout:** Configured with 60,000ms (`PRAGMA busy_timeout=60000`) to queue concurrent writes rather than throwing lock exceptions.
- **Lock-Free Pipeline Execution:** No database transactions are held open across external HTTP requests.
