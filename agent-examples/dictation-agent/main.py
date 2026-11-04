"""Wispr Flow Dictation Agent — Voice-to-polished-text pipeline service.

Follows the VoxLab HTTP agent contract:
    POST /conversation {session_id, message, metadata} ->
        {reply, tool_calls, state, timings, error, interrupted}
"""

from __future__ import annotations

import time
from fastapi import FastAPI
from pydantic import BaseModel, Field

from cleaner import process_dictation
from failure_config import get as get_failure_config, update as update_failure_config

app = FastAPI(title="Wispr Flow Dictation Demo Agent", version="0.1.0")


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
    tool_calls: list[ToolCallOut] = Field(default_factory=list)
    state: dict = Field(default_factory=dict)
    timings: dict = Field(default_factory=dict)
    error: str | None = None
    interrupted: bool = False


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "agent": "dictation-agent",
        "product": "Wispr Flow",
    }


@app.post("/conversation", response_model=ConversationResponse)
def conversation(req: ConversationRequest) -> ConversationResponse:
    start = time.perf_counter()

    # Check for simulated tool failures or interruptions from VoxLab runner
    if req.metadata.get("tool_failure"):
        return ConversationResponse(
            reply="Error: dictation pipeline internal processing failure.",
            tool_calls=[
                ToolCallOut(
                    name="transcribe_clean",
                    args={"raw": req.message},
                    result={"error": "500 Internal Service Error"},
                    status="failure",
                    duration_ms=45,
                )
            ],
            state={"error": True},
            timings={"llm_ms": 50, "tool_ms": 45},
            error="Pipeline crash",
        )

    # Process raw transcript through dictation cleanup (with optional sandbox override)
    cfg_override = req.metadata.get("failure_config")
    cleaned = process_dictation(req.message, config_override=cfg_override)

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    return ConversationResponse(
        reply=cleaned,
        tool_calls=[],
        state={"processed": True, "input_len": len(req.message), "output_len": len(cleaned)},
        timings={"llm_ms": max(20, elapsed_ms), "tts_ms": 0},
        interrupted=bool(req.metadata.get("interrupt")),
    )


@app.get("/admin/failure-config")
def read_failure_config() -> dict:
    return get_failure_config()


@app.post("/admin/failure-config")
def set_failure_config(body: dict) -> dict:
    return update_failure_config(body)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8200)
