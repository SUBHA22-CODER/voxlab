# VoxLab Testing Strategy

## Philosophy
Voice AI agent infrastructure requires a multi-layered testing pyramid. Because voice interactions exhibit non-deterministic stochastic variations, static assertions must be paired with automated evolutionary fuzzing.

---

## The Testing Pyramid

```text
               ▲
              / \
             /   \      Layer 4: Darwin Evolutionary Fuzzing (Genomes, Mutations, ddmin)
            /     \
           /-------\    Layer 3: E2E Scenario Runner & Real-time WebSockets
          /         \
         /-----------\  Layer 2: REST API & Tenant Isolation Integration Tests
        /             \
       /---------------\ Layer 1: Deterministic Heuristic & Math Unit Tests
```

---

## 1. Unit Tests (Backend)
- **Engine Scenarios:** Validates `ScenarioRunner` step dispatch, latency collection, and timeout mechanics.
- **Evaluation Dimensions:** Tests the 5-dimension evaluation engine ($0.30T + 0.25Q + 0.20R + 0.15L + 0.10E$).
- **Wispr Flow Evaluator:** Verifies filler word counting, self-correction intent preservation, and entity extraction.
- **Delta Debugging Minimizer:** Verifies that `ddmin` partitions conversation sequences and finds 1-turn minimal reproductions.

### Run Backend Tests:
```bash
cd backend
python -m pytest -v
```

---

## 2. Integration & API Tests
- Validates JWT authentication lifecycle (`/api/auth/register`, `/api/auth/login`, `/api/auth/me`).
- Tests Agent CRUD operations and AES-GCM credential protection.
- Validates Darwin campaign dispatch, live generation polling, and cancellation.

---

## 3. Frontend Production Build Validation
- Verifies strict TypeScript type-checking across all components, hooks, and API clients.
- Asserts clean Webpack / Next.js production compilation with zero errors:
```bash
cd frontend
npm run build
```

