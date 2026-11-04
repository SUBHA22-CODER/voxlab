# Delta Debugging (ddmin) Failure Minimization

## The Problem
When an adversarial fuzzing campaign discovers an agent crash after a 10-turn conversation, it is difficult for engineers to identify which turn actually caused the failure:
- Was it the prompt on Turn 2?
- Was it the tool call on Turn 5?
- Was it the self-correction on Turn 9?

---

## The ddmin Algorithm in VoxLab

Implemented in `backend/app/darwin/minimizer.py`, Delta Debugging simplifies the failing test case to a **1-turn or minimal multi-turn reproduction**:

1. **Partitioning:** The set of conversation turns is divided into $n$ subsets (initially $n = 2$).
2. **Subset Testing:**
   - Tests each partition subset against the target agent. If the agent still fails, the subset becomes the new baseline.
3. **Complement Testing:**
   - Tests the complement of each partition ($turns \setminus subset$). If the failure persists, the irrelevant subset is eliminated.
4. **Granularity Increase:**
   - If neither subset nor complement reproduces the bug, granularity increases ($n = \min(2n, |turns|)$).
5. **Termination:**
   - Stops when $n > |turns|$ (1-minimal failure sequence achieved).

### Typical Results
- **Original Attack:** 8-10 turns containing conversational noise.
- **Minimized Finding:** 1-2 turns containing only the critical phonetic confusion or self-correction trigger.

