# VoxLab API Reference

Base URL (local dev): `http://localhost:8001` (or `8000` if free).
Authentication: JWT bearer token from `/api/auth/login` or `/api/auth/register`.

## Auth

| Method | Endpoint | Body | Notes |
|---|---|---|---|
| POST | `/api/auth/register` | `{email, password}` | 201 → `{access_token}`; 409 if email taken |
| POST | `/api/auth/login` | `{email, password}` | 200 → `{access_token}`; rate-limited (15/min/IP) |
| GET | `/api/auth/me` | — | Current user |

## Agents

| Method | Endpoint | Notes |
|---|---|---|
| GET | `/api/agents` | List the user's agents (secrets never serialized) |
| POST | `/api/agents` | Register: `{name, endpoint, agent_type, description?, auth_config?, stt/llm/tts_provider?, config?}` |
| GET/PATCH/DELETE | `/api/agents/{id}` | Owner-only; PATCH re-validates + re-encrypts credentials |
| POST | `/api/agents/{id}/connect` | Reachability probe → `{ok, status, detail, latency_ms}` |

Registered endpoints pass an SSRF guard: non-HTTP schemes are rejected;
private/loopback hosts require `ALLOW_LOCAL_ENDPOINTS=true` (enabled by
default for local development, disable for production).

## Agent conversation contract

Your agent receives POSTs at its registered endpoint:

```json
// request
{
  "session_id": "vx-s12-ab12cd34",
  "message": "Check the status of order ORD-1002",
  "metadata": {
    "interrupt": true,                  // turn follows a user interruption
    "inject": {"tool_failure": true},   // scenario asks your tool/API to fail
    "signal": "silence"                 // or "ping" (reply "pong")
  }
}

// response
{
  "reply": "I'm sorry — I'm having trouble reaching our order system…",
  "tool_calls": [{"name": "check_order_status", "args": {}, "status": "error", "duration_ms": 40}],
  "state": {"turns": 3, "escalated": false},
  "timings": {"llm_ms": 120, "tool_ms": 40, "total_ms": 180},
  "error": null
}
```

All response fields except `reply` are optional and default safely. `timings`
feed the trace pipeline stages; `tool_calls` feed deterministic checks and the
event stream.

## Scenarios

| Method | Endpoint | Notes |
|---|---|---|
| GET | `/api/scenarios` | Built-in + the user's own |
| POST | `/api/scenarios` | `{name, category, definition}` |
| GET/DELETE | `/api/scenarios/{id}` | |

Scenario definition format (`scenarios/*.json`):

```json
{
  "name": "Interruption Test",
  "category": "interruption",
  "steps": [
    {"type": "user_message", "content": "Tell me about your services"},
    {"type": "interrupt", "content": "Wait, explain the pricing first"}
  ],
  "expected_behavior": "Agent should handle interruption and answer pricing",
  "latency_budget_ms": 8000,
  "checks": [
    {"type": "reply_contains", "any_of": ["pricing", "$"], "turn": -1},
    {"type": "tool_called", "name": "check_order_status"}
  ]
}
```

Step types: `user_message`, `interrupt`, `tool_failure` (inject on next
turn), `silence`.
Check types: `tool_called`, `tool_not_called`, `latency_under`,
`reply_contains`, `reply_not_contains`, `reply_nonempty`, `state_equals`,
`transcript_similarity`. `turn: -1` = last agent reply, `all_turns: true`
applies to every reply.

## Test runs

| Method | Endpoint | Notes |
|---|---|---|
| POST | `/api/test-runs` | `{agent_id, scenario_ids, weights?}` → 202, runs in background |
| GET | `/api/test-runs` | History |
| GET | `/api/test-runs/{id}` | Detail incl. sessions, evaluations and the report when ready |
| POST | `/api/test-runs/{id}/cancel` | Cancel a queued/running run |
| GET | `/api/test-runs/{id}/report` | Report row (404 until the run completes) |

## Sessions / traces / reports

| Method | Endpoint | Notes |
|---|---|---|
| GET | `/api/sessions/{id}` | Session detail: events (ordered), evaluation, trace |
| GET | `/api/sessions/{id}/traces` | Pipeline trace: per-turn stage durations |
| GET | `/api/reports/{id}` | Full report summary |
| GET | `/api/reports/{a}/compare/{b}` | Component deltas between two runs |

## Playground WebSocket

`WS /ws/playground/{agent_id}?token=<JWT>`

Client → server:
```json
{"type": "text_message", "content": "hello"}
{"type": "voice_transcript", "content": "hello", "stt_ms": 180, "audio_ms": 1400}
{"type": "stop"}
```

Server → client:
```json
{"type": "session_started", "session_id": 41, "trace_id": "…"}
{"type": "agent_message", "content": "Hi!", "latency_ms": 210,
 "tool_calls": [], "state": {}, "error": null,
 "events": [{"sequence": 3, "event_type": "agent_message", "timestamp": "…",
             "duration_ms": 210, "payload": {}}]}
{"type": "error", "message": "Cannot reach agent: …"}
```

Playground sessions persist (source=`playground`) with events + trace and are
viewable in the trace viewer, but are not scored by the benchmark engine.

## Health

`GET /api/health` → `{"status": "ok", "app": "VoxLab", "llm_judge": "heuristic"|"enabled"}`
