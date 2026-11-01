# VoxLab Demo Agent — Customer Support

A standalone FastAPI voice agent that speaks the [VoxLab agent contract]
(../docs/api-reference.md#agent-conversation-contract). It exists so VoxLab
has something to test before external developers connect their own agents —
and so demos can show real, diagnosed failures.

## Capabilities

- Product FAQ (services, pricing, hours, returns)
- Mock order API: check status, cancel (with cancellation confirmation)
- Escalate to human support
- Multi-turn memory (remembers your order ID across topics)

## The failure switches

`failure_config.json` deliberately introduces bad behavior. Each switch maps
to a builtin VoxLab scenario:

| Switch | Broken behavior | Scenario that catches it |
|---|---|---|
| `ignore_interruptions` | Plows on with the previous topic | Interruption Test |
| `crash_on_tool_error` | Returns an empty reply on API 500 | API Failure / Recovery |
| `forget_context` | Re-asks for the order ID every turn | Context Retention / Long Conversation |
| `hinglish_support` | `false` = refuses Hinglish | Hinglish Understanding |

The repo ships the **broken** config. `failure_config.fixed.json` is the fixed
version. Flip switches live with:

```bash
curl -X POST http://localhost:8100/admin/failure-config \
     -H "Content-Type: application/json" \
     -d '{"ignore_interruptions": false}'
curl -X POST http://localhost:8100/admin/reset    # clear sessions
```

> The admin endpoints are unauthenticated by design — this is a localhost
> demo process, not a production service. Never expose port 8100.

## Running

```bash
uvicorn main:app --port 8100
# health: http://localhost:8100/health
```

Register it in VoxLab as `http://localhost:8100/conversation` (the seed
script does this automatically).

## LLM mode (optional)

By default the agent is fully scripted (deterministic, offline, fast). To run
it with an LLM composing replies:

```bash
LLM_DEMO_MODE=llm LLM_API_KEY=... LLM_BASE_URL=... LLM_MODEL=... uvicorn main:app --port 8100
```

Failure switches become system-prompt directives in LLM mode.
