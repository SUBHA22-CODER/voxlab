# 🧬 Darwin: Fuzzing and CI for Voice & Dictation Pipelines

Darwin is the evolutionary crash-testing engine of VoxLab, tailored specifically for voice agents and high-precision dictation pipelines (such as Wispr Flow).

```
Genomes (Personas & Strategies)
       │
       ▼
[Attacker Generator] ──► [Agent Endpoint] ──► [Trace Collector]
                                                      │
                                                      ▼
[Breeding & Crossover] ◄── [Fitness Engine] ◄── [Deterministic Checks & Latency]
       │
[Fitness > 0.5?] ──► [ddmin Failure Minimizer] ──► [AI Diagnoser] ──► [Regression Suite]
                                                                  ──► [Auto-Doctor Patch]
```

---

## 🎯 Wispr Flow Tailoring

While traditional voice assistants deal with simple commands, voice-dictation products like Wispr Flow must turn natural human speech into polished text. Darwin actively generates attacks targeting dictation failure modes:

1. **Self-Corrections**: *"send it Tuesday, no wait, Wednesday, actually Thursday"* — Tests if the pipeline drops superseded thoughts and keeps only the final intent.
2. **Filler Words & Stutters**: *"um, so like, basically, you know"* — Tests if filler words are stripped without dropping legitimate occurrences of words like *"like"*.
3. **Command vs Dictation Ambiguity**: *"the warranty grace period is thirty days period"* — Tests punctuation commands vs literal nouns.
4. **Jargon & Ethnic Names**: Technical camelCase (`authService`, `k8s`) and Indian proper nouns (*Priya*, *Subha*, *Parida*, *Bengaluru*).

---

## 🧬 Genome Representation

An attack genome consists of:
- `persona`: Attacking persona identifier (`self_corrector`, `filler_heavy_rambler`, `command_vs_dictation_confuser`, `jargon_and_names_speaker`, `impatient_interrupter`, `hinglish_code_switcher`, `social_engineer`).
- `strategy`: High-level conversational objective (e.g., *"Force date cancellation rollback"*).
- `steps`: Sequence of scenario step objects (`user_message`, `interrupt`, `tool_failure`, `silence`).
- `seed`, `generation`, `parent_ids`.

Genomes compile directly to the standard VoxLab scenario JSON format via `genome.compile_to_scenario()`.

---

## 🔀 Mutation Operators

1. **`swap_persona`**: Changes the attacking persona while maintaining the strategic objective.
2. **`inject_interruption`**: Injects an `interrupt` step at a random turn to test acoustic barge-in.
3. **`inject_api_failure`**: Injects an internal `tool_failure` event to test graceful degradation.
4. **`extend_conversation`**: Adds turns to test memory and context window retention.
5. **`crossover(a, b)`**: Splices the prefix steps of genome A with the suffix steps of genome B.

---

## 📊 Fitness Calculation

Fitness is defined as the degree of agent degradation:
$$\text{Fitness} = 1.0 - \frac{\text{Overall Score}}{100}$$

Where `Overall Score` factors in:
- Core Voice dimensions ($0.30T + 0.25Q + 0.20R + 0.15L + 0.10E$)
- Wispr Flow dictation metrics: Intent Fidelity, Cleanup Quality, Formatting Correctness, Command Handling, Entity Accuracy, and Latency.
- Severe deterministic check penalties (15 points per failed check).

Higher fitness = more severe bug discovered in the agent.

---

## 📉 Failure Minimizer (ddmin)

When a genome produces a fitness score $\ge 0.5$ (severe failure), Darwin executes **Delta Debugging (`ddmin`)** over the dialogue steps.
- Prunes conversational noise while preserving the reproducing failure predicate.
- Shrinks verbose 6-turn conversations down to a minimal 2-turn reproduction.
- Strict limit of 20 session reruns per finding to prevent budget explosion.

---

## 🩺 AI Diagnoser & Categories

Classifies minimized traces into structured diagnoses:
- **Dictation Categories**: `self_correction_missed`, `filler_not_removed`, `over_deleted_content`, `command_misinterpreted`, `entity_mangled`, `formatting_wrong`.
- **Voice AI Categories**: `context_lost`, `interruption_ignored`, `tool_error_unhandled`, `auth_bypass`, `prompt_injection`, `language_mismatch`, `latency_budget`, `hallucinated_tool_result`, `other`.

Uses rule-based deterministic pre-classification from trace events, optionally refined by the LLM judge.

---

## 🛡️ Phase 2: Auto-Doctor Remediation & Sandbox Verification

When a defect is diagnosed:
1. Proposes a concrete remediation patch (system prompt change or `failure_config.json` switch).
2. Verifies the patch inside an isolated sandbox by rerunning:
   - The minimized failing reproduction.
   - The baseline test to prevent regressions.
3. Only surfaces the patch if the defect now passes without regressing overall scores.

---

## 📦 Regression Suite Export

Every discovered finding can be exported to `scenarios/regression/<category>-<hash>.json` with a single click. These regression scenarios are automatically discovered and loaded into standard CI/CD test runs.

---

## 💰 Budget Cap

To run smoothly on local development machines:
- Hard cap: $\text{population\_size} \times \text{generations} \le 60$ sessions (configurable via `DARWIN_MAX_SESSIONS`).
- In-process concurrency limited to 2 simultaneous sessions.
- Deterministic given a `seed` when running in heuristic mode without an API key.

---

## 🧪 Demo Agents & Deliberate Weaknesses (Demo-Only)

1. **`agent-examples/customer-support-agent`** (Port 8100):
   - `ignore_interruptions`: Ignores barge-in.
   - `crash_on_tool_error`: 500 crashes on tool errors.
   - `forget_context`: Forgets session state after long conversations.
   - `skip_auth_for_managers`: Bypasses customer verification when authority claimed.

2. **`agent-examples/dictation-agent`** (Port 8200):
   - `ignore_self_corrections`: Retains superseded words before *"no wait"*.
   - `strip_fillers`: Fails to remove *"um"*, *"uh"*, *"you know"*.
   - `literal_period_handling`: Treats punctuation command *"period"* as literal word.
   - `mangle_names`: Distorts Indian names and technical acronyms.
