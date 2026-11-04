# Contributing to VoxLab

Thank you for your interest in contributing to VoxLab! We welcome contributions from engineers, AI researchers, and audio developers.

---

## Code of Conduct
By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Development Setup

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/<your-username>/voxlab.git
   cd voxlab
   ```

2. **Backend Setup:**
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   pip install pytest pytest-asyncio pytest-cov ruff
   ```

3. **Frontend Setup:**
   ```bash
   cd ../frontend
   npm install
   ```

4. **Run Local Demo Agents:**
   ```bash
   # Terminal 2: Customer Support Agent
   cd agent-examples/customer-support-agent
   python -m uvicorn main:app --port 8100

   # Terminal 3: Wispr Flow Dictation Agent
   cd agent-examples/dictation-agent
   python -m uvicorn main:app --port 8200
   ```

---

## Engineering Standards

### Python (Backend & Darwin)
- Adhere to **PEP 8** and formatting enforced by `ruff`.
- Strict asynchronous execution: use `async` / `await` for all I/O and HTTP network calls.
- **Never hold open a database write transaction across HTTP network calls** (prevents `database is locked` deadlocks).
- Run linter and tests before committing:
  ```bash
  cd backend
  ruff check .
  pytest -v
  ```

### TypeScript / Next.js (Frontend)
- Strict TypeScript with zero unconstrained `any` types.
- Vanilla Tailwind CSS utility classes; no inline styles.
- Verify production build compiles without errors:
  ```bash
  cd frontend
  npm run build
  ```

---

## Branching & Commit Conventions

- Create descriptive feature branches:
  - `feat/new-persona-strategy`
  - `fix/websocket-event-dedup`
  - `docs/clarify-darwin-evolution`
- Use [Conventional Commits](https://www.conventionalcommits.org/):
  - `feat: add phonetic confusion mutation operator`
  - `fix: resolve race condition in scenario collector`
  - `docs: update system design architecture diagram`
  - `test: add unit tests for ddmin partition complement`

---

## Pull Request Process

1. Ensure all backend unit tests pass: `pytest -q` (109+ tests).
2. Ensure frontend compiles cleanly: `npm run build`.
3. Submit a Pull Request targeting `main`.
4. Provide a clear description of the problem solved, code changes, and test results.
