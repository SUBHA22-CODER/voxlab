# VoxLab Security Controls & Defense in Depth

## 1. Authentication & Tenant Isolation
- **JWT Cryptographic Verification:** All API routes (except `/api/auth/register`, `/api/auth/login`, and `/health`) require a valid `Bearer` token signed with `JWT_SECRET`.
- **Database Row-Level Scoping:** Every query for agents, runs, scenarios, traces, and Darwin findings explicitly filters on `user_id == current_user.id`.

## 2. Cryptographic Storage
- Stored agent authentication configurations (such as custom bearer tokens or API credentials) are encrypted at rest using AES-GCM before database write in `backend/app/core/security.py`.
- Password hashes use PBKDF2 with SHA-256 and unique per-user salts.

## 3. Sandboxed Execution & Timeouts
- All external HTTP calls made by `ScenarioRunner` to voice agents enforce strict connection and read timeouts (default 10s).
- Broken or non-responsive agents fail fast rather than hanging background worker queues.

