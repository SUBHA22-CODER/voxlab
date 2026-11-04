# Darwin Evolutionary Fuzzing Engine

## Overview
**Darwin** is VoxLab's genetic testing system designed specifically for conversational voice agents and voice-to-text dictation pipelines (Wispr Flow).

Instead of relying on fixed human-authored test scripts, Darwin treats test scenarios as evolving **genomes**. Over multiple generations, it searches the combinatorial space of conversational speech disruptions to discover edge cases that cause agents to crash, lose context, hallucinate tools, or fail dictation cleanup.

---

## The Darwin Reliability Lifecycle

```text
  ┌─────────────────────────────────────────────────────────────┐
  │ 1. ATTACK                                                   │
  │ Spawns adversarial population using mutated voice personas  │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ 2. EVALUATE & SELECT                                        │
  │ Measures agent degradation score; preserves elite attackers │
  └──────────────────────────────┬──────────────────────────────┘
                                 │ (If Score < 50%)
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ 3. MINIMIZE (Delta Debugging ddmin)                         │
  │ Strips non-essential conversational turns to find 1-turn bug│
  └──────────────────────────────┬──────────────────────────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ 4. DIAGNOSE                                                 │
  │ Pinpoints root cause (e.g., self-correction, homophone)     │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ 5. LOCK IN (Regression Scenario)                            │
  │ Exports reproducible JSON test into CI suite to prevent bug │
  └─────────────────────────────────────────────────────────────┘
```

---

## Active Attack Personas

1. **Rapid Self-Corrector:** Corrects quantities, dates, names, or addresses mid-utterance (e.g. *"Tuesday, wait no, Wednesday at 4"*).
2. **Homophone & Acoustic Confuser:** Tests phonetically ambiguous vocabulary (*"accept"* vs *"except"*, *"two"* vs *"to"*).
3. **Filler & Hesitation Injector:** Floods pipeline with realistic conversational disfluencies (*"um"*, *"uh"*, *"like"*).
4. **Barge-in Interrupter:** Fires user utterances before agent finishes speaking to test turn-taking state machines.
5. **Context Switcher:** Abruptly shifts domain context and re-queries earlier conversational slots.
