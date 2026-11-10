# VoxLab Baseline Test Report (Phase 0)

> Date: 2026-11-10 · HEAD: `9bd93ef` · Environment: Windows 11 (10.0.26300), Python 3.11.9, pytest 9.2.0, pytest-asyncio

## Command actually executed

```
cd backend
.venv\Scripts\python.exe -m pytest -q
```

## Result

```
........................................................................ [ 66%]
.....................................                                    [100%]
109 passed in 14.56s
```

**109 passed, 0 failed, 0 skipped, 0 errors.** (One pre-existing
`PytestDeprecationWarning` about `asyncio_default_fixture_loop_scope` — cosmetic.)

This matches the repository README badge ("Pytest 109 Passed"). The count
decomposition: 88 `def test_` functions across 12 files; `test_scenarios_json.py`
parametrizes 3 functions over 8 scenario JSON files (24 instances), so the
collected total is 109.

## Coverage map (what the baseline suite actually tests)

| File | Tests | Kind | Notes |
|---|---|---|---|
| `test_api_e2e.py` | 12 | Integration | Auth, agent registry + cross-user isolation, full benchmark flow via `ScriptedAgentAdapter` |
| `test_darwin.py` | 17 | Unit | Genome hashing, mutations, crossover, seed determinism, ddmin, diagnoser categories, fitness, budget clamp |
| `test_darwin_integration.py` | 1 (`integration` marker) | Integration | Full `execute_evolution` campaign vs scripted agent; asserts minimization + regression export |
| `test_evaluation.py` | 15 | Unit | All deterministic check types, latency math, heuristic judge fallbacks |
| `test_adapters.py` | 6 | Unit | HTTP via `httpx.MockTransport`, WS framing |
| `test_security.py` | 11 | Unit | PBKDF2, JWT, Fernet roundtrips + tamper cases |
| `test_endpoint_guard.py` | 6 | Unit | SSRF guard, private/loopback rejection |
| `test_scenario_runner.py` | 6 | Unit | Step types incl. interrupt/tool_failure/silence |
| `test_reports.py` | 8 | Unit | Score formula, category pooling, compare |
| `test_playground.py` | 2 | Integration | WS flow with fake adapter |
| `test_scenarios_json.py` | 25 collected | Unit | Schema + step validation of the 8 builtin scenario JSONs |

## Network / key requirements

**None.** All agent I/O is scripted or mocked at the HTTP-transport layer; every
LLM-dependent path is exercised with `LLMService(api_key="")` (heuristic mode).
The suite is hermetic and safe for CI without secrets.

## Pre-existing gaps (for the 2.0 work)

1. No audio/STT tests — nothing to test yet; VoxLab 2.0 adds them (marked and
   separated: mocked unit tests vs opt-in real-engine integration tests).
2. `arq` imported conditionally in `workers/runner.py` but absent from
   `requirements.txt` (latent import error when `REDIS_URL` set).
3. No coverage measurement in the default run (`pytest-cov` not installed).
4. `asyncio_default_fixture_loop_scope` deprecation warning — set explicitly
   when `pytest.ini` is next touched.

## Regression rule going forward

Any VoxLab 2.0 change that makes this suite fail has broken backward
compatibility and must be fixed before proceeding (commit rule from the master
engineering prompt: existing tests must continue passing).
