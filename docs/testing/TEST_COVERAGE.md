# Test Coverage Report

**Environment:** Python 3.11 / Pytest 8.x / FastAPI / Next.js 16  
**Execution Date:** November 4, 2026  
**Status:** :white_check_mark: 109 Passed, 0 Failed  

---

## Test Execution Summary

```text
============================== test session starts ==============================
platform win32 -- Python 3.11.9, pytest-8.3.4, pluggy-1.5.0
rootdir: C:\Users\Subha Prasana Parida\OneDrive\Desktop\wisprflow\backend
plugins: anyio-4.8.0, asyncio-0.24.0, cov-6.0.0
collected 109 items

tests/test_api_e2e.py .................................................... [ 47%]
tests/test_darwin.py ..............                                        [ 60%]
tests/test_darwin_integration.py ........                                  [ 67%]
tests/test_evaluation.py ...................................              [100%]

============================== 109 passed in 18.42s =============================
```

---

## Coverage by Domain

| Domain | Tested Modules | Pass Rate |
| :--- | :--- | :--- |
| **Authentication & Auth** | `app/api/auth.py`, `app/core/security.py` | 100% |
| **Agent Registry** | `app/api/agents.py`, `app/models/agent.py` | 100% |
| **Scenario Execution** | `app/engine/scenario_runner.py` | 100% |
| **Trace Collection** | `app/services/trace_collector.py` | 100% |
| **Evaluation Engine** | `app/services/evaluation.py` | 100% |
| **Darwin Fuzzing Engine** | `app/darwin/evolution.py`, `app/darwin/genome.py` | 100% |
| **Delta Debugging Minimizer** | `app/darwin/minimizer.py` | 100% |
| **Wispr Flow Cleaner Agent** | `agent-examples/dictation-agent/` | 100% |
