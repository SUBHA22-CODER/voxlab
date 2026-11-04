# Testing Strategy & Test Suite Guide

> **Assumptions:**
> - Unit and integration tests run via `pytest` and `pytest-asyncio`.
> - Frontend tests and build validation run via `next build` and TypeScript checks.

---

## 1. Test Suite Structure
```
backend/tests/
├── conftest.py                   # Async database session & client fixtures
├── scripted_agent.py             # Deterministic mock voice agent
├── test_darwin.py                # Darwin unit tests (genome, personas, minimizer, diagnoser)
├── test_darwin_integration.py    # Multi-generation end-to-end evolution loop test
├── test_evaluation.py            # Dictation and intent scoring test suite
├── test_api_e2e.py               # REST API end-to-end integration tests
├── test_adapters.py              # HTTP and WebSocket agent adapters
├── test_security.py              # Auth and Fernet credential encryption
└── test_endpoint_guard.py        # SSRF and private IP blocking tests
```

---

## 2. Running Backend Tests
Execute the full suite from `backend/`:
```bash
cd backend
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pytest -v
```

### Running Specific Test Groups
- **Darwin Fuzzing Tests Only:**
  ```bash
  pytest -q tests/test_darwin.py tests/test_darwin_integration.py
  ```
- **Evaluation & Scoring Tests Only:**
  ```bash
  pytest -q tests/test_evaluation.py
  ```

---

## 3. Running Frontend Checks
Validate TypeScript types and Next.js production build:
```bash
cd frontend
npm run build
```
Acceptance criteria: 0 TypeScript errors, 13 static/dynamic routes compiled cleanly.
