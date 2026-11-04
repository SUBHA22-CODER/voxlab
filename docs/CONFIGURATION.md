# VoxLab Configuration Reference

All environment variables used across backend, frontend, and demo agents are documented here.

## Backend Environment Variables (`backend/.env`)

| Variable | Description | Required | Default | Example |
| :--- | :--- | :--- | :--- | :--- |
| `DATABASE_URL` | Async SQLAlchemy database connection string | No | `sqlite+aiosqlite:///./voxlab.db` | `sqlite+aiosqlite:///./voxlab.db` |
| `JWT_SECRET` | Secret key used for signing user authentication tokens | Yes in Prod | `super-secret-development-jwt-key-voxlab` | `openssl rand -hex 32` |
| `ALGORITHM` | JWT signing algorithm | No | `HS256` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Lifetime of JWT bearer tokens | No | `1440` (24 hours) | `1440` |
| `GROQ_API_KEY` | Optional API key for high-speed LLM judge evaluations and root-cause diagnoses | No | None (heuristic fallback used) | `gsk_...` |
| `OPENAI_API_KEY` | Optional fallback LLM provider | No | None | `sk-...` |
| `DARWIN_MAX_SESSIONS` | Hard budget cap on Darwin evolution sessions per campaign | No | `60` | `60` |
| `ENCRYPTION_KEY` | 32-byte key for AES-GCM agent credential encryption | Yes in Prod | Dev default key | Base64-encoded 32 bytes |

---

## Frontend Environment Variables (`frontend/.env.local`)

| Variable | Description | Required | Default |
| :--- | :--- | :--- | :--- |
| `NEXT_PUBLIC_API_URL` | Base URL of the backend FastAPI service | No | `http://localhost:8001` |
| `NEXT_PUBLIC_WS_URL` | WebSocket URL for real-time playground audio streaming | No | `ws://localhost:8001` |

---

## Security Guidelines

- Never commit `.env` or `.env.local` files to version control.
- In production, replace `JWT_SECRET` and `ENCRYPTION_KEY` with cryptographically secure random values.
- If no external LLM API key is supplied, VoxLab seamlessly activates its deterministic NLP heuristic evaluators.
