"""Pydantic schemas for API request/response bodies."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


# --- Auth ---

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Agents ---

class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    endpoint: str = Field(min_length=8, max_length=1024)
    agent_type: str = "http"  # http | websocket
    # {"type": "bearer", "token": "..."} or {"headers": {...}} — encrypted at rest.
    auth_config: dict | None = None
    stt_provider: str = ""
    llm_provider: str = ""
    tts_provider: str = ""
    config: dict = Field(default_factory=dict)


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    endpoint: str | None = None
    agent_type: str | None = None
    auth_config: dict | None = None
    stt_provider: str | None = None
    llm_provider: str | None = None
    tts_provider: str | None = None
    config: dict | None = None


class AgentOut(BaseModel):
    id: int
    name: str
    description: str
    endpoint: str
    agent_type: str
    connection_status: str
    stt_provider: str
    llm_provider: str
    tts_provider: str
    config: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class ConnectionTestResult(BaseModel):
    ok: bool
    status: str
    detail: str
    latency_ms: int | None = None


# --- Scenarios ---

class ScenarioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=64)
    definition: dict[str, Any]


class ScenarioOut(BaseModel):
    id: int
    name: str
    category: str
    definition: dict
    is_builtin: bool
    user_id: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Test runs ---

class TestRunCreate(BaseModel):
    agent_id: int
    scenario_ids: list[int]
    weights: dict[str, float] | None = None
    latency_budget_ms: int | None = None


class SessionSummary(BaseModel):
    id: int
    scenario_id: int | None
    scenario_name: str | None = None
    status: str
    started_at: datetime
    finished_at: datetime | None
    evaluation: dict | None = None

    model_config = {"from_attributes": True}


class TestRunOut(BaseModel):
    id: int
    agent_id: int
    status: str
    progress: int
    total_sessions: int
    config: dict
    error: str | None
    started_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class TestRunDetail(TestRunOut):
    sessions: list[SessionSummary] = []
    report: dict | None = None


# --- Sessions / events / traces ---

class EventOut(BaseModel):
    id: int
    sequence: int
    trace_id: str
    event_type: str
    timestamp: datetime
    duration_ms: int | None
    payload: dict

    model_config = {"from_attributes": True}


class SessionOut(BaseModel):
    id: int
    test_run_id: int | None
    agent_id: int
    scenario_id: int | None
    trace_id: str
    status: str
    source: str
    started_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class SessionDetail(SessionOut):
    events: list[EventOut] = []
    evaluation: dict | None = None
    trace: dict | None = None


class TraceOut(BaseModel):
    session_id: int
    trace_id: str
    trace_data: dict

    model_config = {"from_attributes": True}


# --- Reports ---

class ReportOut(BaseModel):
    id: int
    test_run_id: int
    score: float
    summary: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class ComparisonResponse(BaseModel):
    baseline: dict
    candidate: dict
    deltas: dict
