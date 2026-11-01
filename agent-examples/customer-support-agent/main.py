"""VoxLab demo customer-support voice agent.

Speaks the VoxLab HTTP agent contract:
    POST /conversation {session_id, message, metadata} ->
        {reply, tool_calls, state, timings, error, interrupted}

Failure switches live in failure_config.json (mutable via /admin/failure-config):
deliberately break the agent, benchmark it with VoxLab, fix the config,
rerun and show the improvement.

Run: uvicorn main:app --host 0.0.0.0 --port 8100
"""

from __future__ import annotations

import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from brain import Brain, SessionState
from failure_config import get as get_failure_config
from failure_config import load, update as update_failure_config

app = FastAPI(title="VoxLab Demo Agent — Customer Support", version="0.1.0")

brain = Brain()
sessions: dict[str, SessionState] = {}


class ConversationRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = ""
    metadata: dict = Field(default_factory=dict)


class ToolCallOut(BaseModel):
    name: str
    args: dict
    result: object
    status: str
    duration_ms: int


class ConversationResponse(BaseModel):
    reply: str
    tool_calls: list[ToolCallOut]
    state: dict
    timings: dict
    error: str | None = None
    interrupted: bool = False


def _session(session_id: str) -> SessionState:
    if session_id not in sessions:
        sessions[session_id] = SessionState()
    return sessions[session_id]


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "agent": "customer-support-demo", "mode": "llm" if brain.use_llm else "scripted"}


@app.post("/conversation", response_model=ConversationResponse)
async def conversation(body: ConversationRequest) -> ConversationResponse:
    started = time.perf_counter()
    session = _session(body.session_id)

    reply, tool_calls, error = await brain.respond(session, body.message, body.metadata)
    interrupted = bool(body.metadata.get("interrupt")) and get_failure_config()["ignore_interruptions"]

    return ConversationResponse(
        reply=reply,
        tool_calls=[
            ToolCallOut(
                name=call.name,
                args=call.args,
                result=call.result,
                status=call.status,
                duration_ms=call.duration_ms,
            )
            for call in tool_calls
        ],
        state={
            "turns": session.turns,
            "order_id": session.order_id,
            "escalated": session.escalated,
            "cancelled": session.cancelled,
        },
        timings={
            "llm_ms": int((time.perf_counter() - started) * 1000),
            "tool_ms": sum(call.duration_ms for call in tool_calls),
            "total_ms": int((time.perf_counter() - started) * 1000),
        },
        error=error,
        interrupted=interrupted,
    )


# --- Demo administration (single-process demo, not production-safe) ---


class FailureConfigUpdate(BaseModel):
    ignore_interruptions: bool | None = None
    crash_on_tool_error: bool | None = None
    forget_context: bool | None = None
    hinglish_support: bool | None = None


@app.get("/admin/failure-config")
async def read_failure_config() -> dict:
    return get_failure_config()


@app.post("/admin/failure-config")
async def write_failure_config(body: FailureConfigUpdate) -> dict:
    return update_failure_config(body.model_dump(exclude_none=True))


@app.post("/admin/reset")
async def reset() -> dict:
    """Clear conversation state and restore the on-disk failure config."""
    sessions.clear()
    load()
    return {"status": "reset", "failure_config": get_failure_config()}
