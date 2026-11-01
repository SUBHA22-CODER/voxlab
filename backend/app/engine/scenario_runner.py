"""Scenario execution (spec Module C).

Executes a scenario definition's steps against an agent adapter, recording
every pipeline event with the TraceCollector and producing a structured
RunOutput for the evaluation engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.adapters.base import AgentTurnResult, VoiceAgentAdapter
from app.engine.trace_collector import (
    EVENT_AGENT_MESSAGE,
    EVENT_ERROR,
    EVENT_INTERRUPTION,
    EVENT_SILENCE,
    EVENT_TOOL_CALL,
    EVENT_TOOL_FAILURE_INJECTED,
    EVENT_USER_MESSAGE,
    TraceCollector,
)


@dataclass
class RunOutput:
    transcript: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    final_state: dict = field(default_factory=dict)
    turn_latencies_ms: list[int] = field(default_factory=list)
    injected_tool_failures: int = 0
    interrupts: int = 0
    error_turns: list[int] = field(default_factory=list)
    agent_error: str | None = None


class ScenarioRunner:
    def __init__(self, adapter: VoiceAgentAdapter, definition: dict, collector: TraceCollector):
        self.adapter = adapter
        self.definition = definition
        self.collector = collector

    async def run(self) -> RunOutput:
        output = RunOutput()
        pending_inject: dict | None = None

        for step in self.definition.get("steps", []):
            step_type = step.get("type", "user_message")

            if step_type == "tool_failure":
                pending_inject = {"tool_failure": True}
                output.injected_tool_failures += 1
                self.collector.record(
                    EVENT_TOOL_FAILURE_INJECTED,
                    {"note": "next agent turn will observe a failing tool/API"},
                )
                continue

            if step_type == "interrupt":
                output.interrupts += 1
                self.collector.record(
                    EVENT_INTERRUPTION,
                    {"content": step.get("content", "")},
                )
                await self._execute_turn(
                    step.get("content", ""),
                    _with_inject({"interrupt": True}, pending_inject),
                    output,
                    kind="interrupt",
                )
                pending_inject = None
                continue

            if step_type == "silence":
                self.collector.record(EVENT_SILENCE, {"note": "user went silent"})
                await self._execute_turn(
                    "", _with_inject({"signal": "silence"}, pending_inject), output, kind="silence"
                )
                pending_inject = None
                continue

            # default: user_message
            await self._execute_turn(
                step.get("content", ""), _with_inject(None, pending_inject), output, kind="user_message"
            )
            pending_inject = None

        return output

    async def _execute_turn(
        self,
        content: str,
        metadata: dict | None,
        output: RunOutput,
        kind: str,
    ) -> AgentTurnResult:
        turn_index = len(output.transcript) // 2 + 1
        self.collector.begin_turn(turn_index)

        payload_content = content if kind != "silence" else "(silence)"
        self.collector.record(
            EVENT_USER_MESSAGE, {"content": payload_content, "kind": kind}
        )

        result = await self.adapter.send_message(content, metadata)

        timings = result.timings or {}
        self.collector.stage("agent_processing", timings.get("llm_ms"), "agent turn")
        for tool_call in result.tool_calls:
            self.collector.record(
                EVENT_TOOL_CALL,
                {
                    "name": tool_call.get("name"),
                    "args": tool_call.get("args"),
                    "status": tool_call.get("status", "success"),
                    "result": _summarize(tool_call.get("result")),
                },
                duration_ms=tool_call.get("duration_ms"),
            )
        self.collector.stage("tool_execution", timings.get("tool_ms"))
        e2e_ms = int(timings.get("total_ms") or 0)
        self.collector.stage("e2e", e2e_ms, kind)

        self.collector.record(
            EVENT_AGENT_MESSAGE,
            {"content": result.reply, "interrupted": result.interrupted},
            duration_ms=e2e_ms,
        )
        if result.error:
            self.collector.record(EVENT_ERROR, {"error": result.error, "turn": turn_index})

        output.transcript.append(
            {"role": "user", "content": content, "turn": turn_index, "kind": kind}
        )
        output.transcript.append(
            {"role": "agent", "content": result.reply, "turn": turn_index, "latency_ms": e2e_ms}
        )
        output.turn_latencies_ms.append(e2e_ms)
        for tool_call in result.tool_calls:
            output.tool_calls.append({"turn": turn_index, **tool_call})
        if result.state:
            output.final_state = result.state
        if result.error:
            output.error_turns.append(turn_index)
            output.agent_error = result.error
        self.collector.end_turn()
        return result


def _with_inject(base: dict | None, inject: dict | None) -> dict:
    """Compose the per-turn metadata per the documented agent contract."""
    metadata = dict(base or {})
    if inject:
        metadata["inject"] = inject
    return metadata


def _summarize(value, limit: int = 200) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."
