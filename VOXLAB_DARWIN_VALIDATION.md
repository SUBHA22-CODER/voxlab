# Darwin Engine Validation & Anti-Hardcoding Report

**Target Scope:** `backend/app/darwin/` (Evolution, Genome, Fitness, Diagnoser, Minimizer, Patcher, Regression)  
**Verification Method:** Empirical execution against live agents and automated regression tests.

---

## 1. Evolution Mechanics & Genome Representation
* **Population Initialization:** Generation 0 initialized with configured population size (default 6, clamped to budget).
* **Genome Operators Tested:**
  - `swap_persona`: Changes attacking profile while preserving dialogue structure.
  - `inject_interruption`: Inserts speech barge-in at strategic turns.
  - `inject_api_failure`: Stresses tool recovery by injecting synthetic downstream 500s.
  - `extend_conversation`: Lengthens conversation to stress multi-turn context retention.
  - `crossover`: Splices parent step sequences into valid offspring.
* **Seed Determinism:** Verified that identical seeds produce bit-for-bit identical mutation trajectories.

---

## 2. Adversarial Personas & Real-World Voice Attack Vectors
All 7 active personas verified:
1. `self_corrector`: Stresses intent rewriting mid-utterance (*"Tuesday, wait no, Wednesday"*).
2. `filler_heavy_rambler`: Tests speech cleanup against verbal crutches (*"um"*, *"uh"*, *"you know"*).
3. `command_vs_dictation_confuser`: Evaluates punctuation commands vs literal content (*"grace period period"*).
4. `jargon_and_names_speaker`: Dictates Indian names, camelCase variables, and enterprise acronyms.
5. `impatient_interrupter`: Forces agent to yield speech on barge-in.
6. `hinglish_code_switcher`: Evaluates mixed Hindi-English grammar and idioms.
7. `social_engineer`: Tests authorization and prompt injection defenses.

---

## 3. Failure Minimization (`ddmin`) Correctness
* **Algorithm:** Zeller's Delta Debugging adapted for conversational step sequences.
* **Granularity Progression:** Starts at $n=2$, splits into chunks, tests subsets and complements, doubling $n$ up to sequence length.
* **Bug Fix Applied:** Partition complement calculation was corrected from value-equality filtering (`[s for s in steps if s not in sub]`) to positional index-based chunk slicing (`[s for j, chunk in enumerate(subsets) if j != i for s in chunk]`), preventing accidental removal of duplicate steps.
* **Empirical Verification:** 3-step and 4-step adversarial attacks successfully reduced to 1-minimal reproducing scenarios in $\le 12$ evaluations.

---

## 4. Root Cause Diagnosis & Anti-Hardcoding Remediation
* **Audit Finding:** The initial diagnoser and fitness functions contained hardcoded checks checking specifically for strings `"tuesday"`, `"wednesday"`, and `"50"`.
* **Remediation Applied:**
  - Generalized self-correction detection to extract candidate superseded tokens from utterance prefixes preceding markers (`"no wait"`, `"scratch that"`, `"wait no"`, `"actually"`).
  - Generalized verbal filler detection and causal trace event slicing.
  - Verified event sequence `0` is never dropped due to falsy evaluation.
  - Set `heuristic: true` on rule-based diagnoses to ensure full transparency.

---

## 5. Regression Library & CI Export
* **Export Endpoint:** `POST /api/darwin/findings/{id}/export`
* **Artifact Output:** Serializes minimized finding into `scenarios/regression/<category>-<hash>.json`.
* **Runner Verification:** Exported JSON scenarios immediately loadable and executable by standard `ScenarioRunner`, consistently reproducing the isolated defect.

---

## 6. Budget & Reliability Guardrails
* **Hard Cap:** Strict 60-session budget cap enforced (`DARWIN_MAX_SESSIONS = 60`).
* **Cancellation:** Active runs cancel cleanly when requested via `POST /api/darwin/runs/{id}/cancel`.
* **Crash Resilience:** If target agent crashes or becomes unreachable mid-campaign, the run safely transitions to `partial` or `failed` without orphan worker tasks.

