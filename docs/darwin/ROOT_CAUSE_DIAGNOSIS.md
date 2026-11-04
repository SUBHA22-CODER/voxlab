# Root Cause Diagnosis & Patch Proposal

## Automated Root-Cause Analysis

Once a failure is minimized, `backend/app/darwin/diagnoser.py` analyzes:
1. Minimized scenario turns.
2. Complete trace event logs.
3. Transcript outputs.
4. Failed deterministic assertions.

---

## Failure Categories

| Category | Diagnosis Description | Typical Trigger |
| :--- | :--- | :--- |
| `SELF_CORRECTION_MISSED` | Pipeline output includes both rejected and corrected phrases. | *"Tuesday, wait no, Wednesday"* |
| `FILLER_NOT_REMOVED` | Stutters or vocal fillers leaked into final text. | *"Um, uh, please call back"* |
| `CONTEXT_LOST` | Agent forgot an earlier entity or slot binding. | Long multi-turn conversation |
| `TOOL_ERROR_UNHANDLED` | Agent crashed on invalid parameter or timeout. | Missing API response |
| `HALLUCINATION` | Agent claimed capabilities or made tool calls not in spec. | Ambiguous instructions |

---

## Patch Proposal & Verification

When an LLM judge is configured (or via deterministic pattern templates), the diagnoser generates:
- **Root Cause Summary:** Clear explanation of why the failure occurred.
- **System Prompt Patch Proposal:** Targeted adjustment to system prompt or formatting rules.
- **Verification (`POST /api/darwin/findings/{id}/verify-patch`):** Executes the minimized scenario using the proposed system prompt in a test sandbox and measures score improvement before and after.
