# VoxLab Evaluation Methodology

Every benchmark score VoxLab produces is decomposed, weighted and explained.
This document defines exactly how each number is calculated.

## The scoring formula

```
Score = 0.30·T + 0.25·Q + 0.20·R + 0.15·L + 0.10·E
```

| Component | Meaning | Source |
|---|---|---|
| **T** | Task completion | Deterministic checks pass rate per session, averaged |
| **Q** | Response quality | LLM judge (relevance) or heuristic fallback |
| **R** | Context retention | Context-heavy sessions (context_retention, long_conversation) when present, else all sessions |
| **L** | Latency | Per-turn score vs the scenario's latency budget |
| **E** | Error recovery | Failure scenarios (tool_failure, recovery, interruption) when present |

Weights are configurable per test run (`weights` on `POST /api/test-runs`)
and are printed with every report so scores stay comparable only under
identical conditions.

## Layer 1 — deterministic checks

Declared per scenario, evaluated on the recorded conversation:

- `tool_called` / `tool_not_called` — the agent's observed tool calls
- `reply_contains` / `reply_not_contains` — substring assertions per turn
  (e.g. refuses Hinglish, re-asks for the order ID, plows through an
  interruption)
- `reply_nonempty` — no empty/crashed turns
- `latency_under` — per-turn wall-clock budget
- `state_equals` — final agent state (e.g. `escalated: false`)
- `transcript_similarity` — for audio scenarios, browser-transcribed input vs
  an expected utterance (difflib ratio)

A session's **T** is the percentage of its checks that passed. Failed checks
are listed in the report with the evidence that failed them.

## Layer 2 — AI-based evaluation

When `LLM_API_KEY` is configured (any OpenAI-compatible provider), an LLM
judge rates each session 0–100 on relevance, context retention, instruction
following and naturalness, given the scenario's expected behavior and the full
transcript. The judge's notes are attached to failures.

**Heuristic fallback (no key).** Without a judge, transparent rules apply:

- **Q (quality)**: −30 per empty reply, −20 per error turn, −15 if replies are
  trivially short, −20 for verbatim repetition.
- **R (context)**: the signature context failure is re-asking for information
  the user already gave; two clarification questions about the same topic
  (order, email, name…) cost −40. Identical answers to identical questions do
  *not* count as failures. Polite offers ("Anything else I can help with?")
  are excluded.
- Sessions scored by heuristics are labeled `judge_mode: heuristic` on the
  report — never presented as AI evaluation.

## Latency (L)

Per turn: `min(100, 100 × latency_budget_ms / actual_ms)`, averaged across
turns. A turn at exactly the budget scores 100; double the budget scores 50.
Budgets default to 5000 ms and are set per scenario (8000 ms for the shipped
suite to accommodate LLM-backed agents).

Stage timings (STT / LLM / tool / TTS) are recorded from the agent's own
`timings` where available. Stage durations can overlap in streaming systems,
so totals use measured per-turn wall-clock durations and reports label the
breakdown as illustrative rather than a strict sum.

## Error recovery (E)

Scored meaningfully only where something actually went wrong:

- An injected tool/API failure (scenario `tool_failure` step) sets the bar:
  100 for a composed, non-empty, graceful reply; 0 if the agent errored.
- Sessions with nothing to recover from contribute their own error-free score.
- If a run includes dedicated failure scenarios, E averages those; otherwise
  it falls back to the global error-free rate.

## Failure diagnosis

The report lists every failed session with:
the exact deterministic checks that failed (with their observed evidence),
judge notes when available, and a link to the session's trace — the timeline
of pipeline stages and events showing *where* the turn went wrong.

## Known limits

- Text-first: accent/noise robustness requires real audio scenarios (declared
  in the format, deferred in the MVP).
- Heuristic Q/R are intentionally conservative; treat heuristic-mode scores
  as smoke-test signals, not absolutes.
- Benchmarks are only comparable across runs with the same scenarios, budgets
  and weights — the report surfaces all three for this reason.
