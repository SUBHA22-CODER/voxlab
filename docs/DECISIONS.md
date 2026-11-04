# Architecture Decision Records (ADRs)

---

## ADR 001: SQLite WAL Mode & Transaction Decoupling for Local Dev
- **Status:** Accepted & Implemented.
- **Context:** Parallel Darwin candidate sessions were causing `sqlite3.OperationalError: database is locked` during concurrent execution when transactions remained open across agent network I/O.
- **Decision:**
  1. Enable SQLite WAL journal mode (`PRAGMA journal_mode=WAL`) and `PRAGMA busy_timeout=60000`.
  2. Decouple candidate evaluation completely: perform scenario generation, agent network calls, and fitness scoring in memory.
  3. Execute database commits in isolated, sub-5ms transaction windows after network calls finish.
- **Consequences:** Completely eliminated database lock deadlocks; enables smooth local execution without requiring an external PostgreSQL instance.

---

## ADR 002: Deterministic Heuristic Fallbacks for Adversarial Generation
- **Status:** Accepted & Implemented.
- **Context:** External LLM APIs (e.g. Groq free tier) encounter HTTP 429 rate limits or network blips during high-volume fuzzing campaigns.
- **Decision:** The attacker materialization pipeline uses `max_retries=1` and `timeout=10.0s`. If an LLM request fails or times out, the engine falls back instantly to built-in persona heuristic utterance banks.
- **Consequences:** Darwin campaigns never hang or fail due to external API outages.

---

## ADR 003: Unified Animated Authentication Interface
- **Status:** Accepted & Implemented.
- **Context:** Separate plain login views broke visual immersion and caused user confusion when switching between signup and signin.
- **Decision:** Consolidate authentication into a single animated page (`/register`) with in-page tab switching between "Create Account" and "Sign In", while automatically redirecting `/login` and `/` to this unified experience.
- **Consequences:** Consistent, state-of-the-art developer onboarding with zero jarring page reloads.
