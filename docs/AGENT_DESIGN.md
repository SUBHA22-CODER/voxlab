# Agent Design & Persona Specifications

> **Assumptions:**
> - Agents follow the standardized conversational JSON schema: `{ "session_id": str, "message": str }` -> `{ "reply": str, "tool_calls": list, "state": dict, "timings": dict }`.
> - Personas simulate both conversational voice interactions and voice-to-text dictation pipelines.

---

## 1. Adversarial Attack Personas

### 1.1 Self-Corrector (`self_corrector`)
- **Role:** Simulates rapid mid-sentence intent modifications and mind changes.
- **Attack Strategy:** "Date/time correction", "Recipient switch", "Action reversal".
- **Inputs:** Conversation context; target agent's previous confirmations.
- **Outputs:** Utterances containing correction markers: `"Schedule for Tuesday, wait, make it Wednesday, actually Thursday at 4 PM"`.
- **Expected Pipeline Behavior:** Final cleaned text or action MUST only reflect the final intent ("Thursday at 4 PM"), dropping superseded fragments.
- **Failure Taxonomy:** `self_correction_missed`.

### 1.2 Filler-Heavy Rambler (`filler_heavy_rambler`)
- **Role:** Simulates speech with excessive hesitation, fillers, and false starts.
- **Attack Strategy:** Filler dilution, natural 'like' as comparison vs filler.
- **Inputs:** Target domain context.
- **Outputs:** Utterances packed with `"um", "uh", "you know", "like, basically, I wanted to..."`.
- **Expected Pipeline Behavior:** Clean text output with all disfluencies stripped while preserving semantic content.
- **Failure Taxonomy:** `filler_not_removed`.

### 1.3 Command-vs-Dictation Confuser (`command_vs_dictation_confuser`)
- **Role:** Tests the boundary between literal text and formatting/control instructions.
- **Attack Strategy:** Ambiguous punctuations and newline commands.
- **Inputs:** Dictation context.
- **Outputs:** `"Dear team period new line please delete that last sentence and add an exclamation mark"`.
- **Expected Pipeline Behavior:** Correctly applies punctuation and structural changes without typing out literal words like `"period"`.
- **Failure Taxonomy:** `command_misinterpreted`.

### 1.4 Jargon and Names Speaker (`jargon_and_names_speaker`)
- **Role:** Tests vocabulary recognition of acronyms, camelCase code symbols, and domain entities.
- **Outputs:** Names with unusual phonetic spellings (`"wisprflow"`, `"PostgreSQL"`, `"DeepSeek-R1"`, `"Srinivasa"`).
- **Expected Pipeline Behavior:** Preserves capitalization and accurate phonetic mapping.
- **Failure Taxonomy:** `entity_mangled`.

### 1.5 Impatient Interrupter (`impatient_interrupter`)
- **Role:** Barge-in conversational agent that cuts off output mid-speech.
- **Failure Taxonomy:** `barge_in_dropped`.

---

## 2. Agent Failure Handling & Handoff Rules
1. **Fallback to Deterministic Heuristics:** If LLM rate limits (HTTP 429) occur, the attacker immediately falls back to built-in persona pattern banks without failing the campaign.
2. **Timeout Circuit Breakers:** Per-turn HTTP timeout is strictly enforced at 15 seconds. If an agent hangs, `RunOutput(agent_error="Timeout")` is captured and scored as high adversarial fitness.
3. **Sandbox Isolation:** Patcher runs sandbox verifications against temporary clones to prevent corrupting active agent configurations.
