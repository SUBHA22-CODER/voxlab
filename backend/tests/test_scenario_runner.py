"""Tests for the scenario runner: step execution and event recording."""

from app.engine.scenario_runner import ScenarioRunner
from app.engine.trace_collector import TraceCollector
from tests.scripted_agent import ScriptedAgentAdapter


def make_runner(definition: dict, adapter: ScriptedAgentAdapter):
    collector = TraceCollector(session_id=1, trace_id="trace-test")
    return ScenarioRunner(adapter, definition, collector), collector


class TestScenarioRunner:
    async def test_user_message_steps_produce_transcript_and_events(self):
        adapter = ScriptedAgentAdapter(
            {"hello": {"reply": "Hi! How can I help?", "state": {"turns": 1}}}
        )
        await adapter.connect()
        definition = {
            "steps": [{"type": "user_message", "content": "hello"}],
        }
        runner, collector = make_runner(definition, adapter)
        output = await runner.run()

        assert adapter.connected is True
        assert [t["content"] for t in output.transcript if t["role"] == "user"] == ["hello"]
        assert [t["content"] for t in output.transcript if t["role"] == "agent"] == ["Hi! How can I help?"]
        assert output.final_state == {"turns": 1}
        assert len(output.turn_latencies_ms) == 1

        event_types = [e["event_type"] for e in collector._events]
        assert "user_message" in event_types
        assert "agent_message" in event_types
        assert "session_ended" not in event_types  # orchestrator adds that

    async def test_tool_failure_step_injects_on_next_message(self):
        adapter = ScriptedAgentAdapter()
        definition = {
            "steps": [
                {"type": "tool_failure"},
                {"type": "user_message", "content": "check my order"},
            ],
        }
        runner, collector = make_runner(definition, adapter)
        await runner.run()

        assert output_injected(collector) is True
        assert adapter.turns[0][1] == {"inject": {"tool_failure": True}}
        assert output_count_matches(collector, "tool_failure_injected", 1)

    async def test_interrupt_step_sends_interrupt_metadata(self):
        adapter = ScriptedAgentAdapter()
        definition = {
            "steps": [
                {"type": "user_message", "content": "tell me about services"},
                {"type": "interrupt", "content": "wait, pricing first"},
            ],
        }
        runner, collector = make_runner(definition, adapter)
        await runner.run()

        assert adapter.turns[1][1].get("interrupt") is True
        event_types = [e["event_type"] for e in collector._events]
        assert "interruption" in event_types

    async def test_silence_step_sends_signal(self):
        adapter = ScriptedAgentAdapter()
        definition = {
            "steps": [
                {"type": "user_message", "content": "hi"},
                {"type": "silence"},
            ],
        }
        runner, collector = make_runner(definition, adapter)  # noqa: RUF059 - fixture parity with other tests
        await runner.run()

        assert adapter.turns[1][0] == ""
        assert adapter.turns[1][1].get("signal") == "silence"

    async def test_errors_are_recorded_per_turn(self):
        adapter = ScriptedAgentAdapter(
            {"hello": {"reply": "", "error": "mock_api_failure"}}
        )
        definition = {"steps": [{"type": "user_message", "content": "hello"}]}
        runner, collector = make_runner(definition, adapter)
        output = await runner.run()

        assert output.error_turns == [1]
        assert output.agent_error == "mock_api_failure"
        event_types = [e["event_type"] for e in collector._events]
        assert "error" in event_types

    async def test_tool_calls_accumulate_across_turns(self):
        adapter = ScriptedAgentAdapter(
            {
                "check": {
                    "reply": "Order shipped.",
                    "tool_calls": [
                        {"name": "check_order_status", "args": {"order_id": "ORD-1"}, "status": "success", "duration_ms": 40}
                    ],
                },
                "cancel": {
                    "reply": "Cancelled.",
                    "tool_calls": [
                        {"name": "cancel_order", "args": {"order_id": "ORD-1"}, "status": "success", "duration_ms": 30}
                    ],
                },
            }
        )
        definition = {
            "steps": [
                {"type": "user_message", "content": "check"},
                {"type": "user_message", "content": "cancel"},
            ],
        }
        runner, collector = make_runner(definition, adapter)
        output = await runner.run()

        assert [tc["name"] for tc in output.tool_calls] == ["check_order_status", "cancel_order"]
        assert output.tool_calls[0]["turn"] == 1
        assert output.tool_calls[1]["turn"] == 2
        event_types = [e["event_type"] for e in collector._events]
        assert event_types.count("tool_call") == 2


def output_injected(collector: TraceCollector) -> bool:
    return any(e["event_type"] == "tool_failure_injected" for e in collector._events)


def output_count_matches(collector: TraceCollector, event_type: str, count: int) -> bool:
    return sum(1 for e in collector._events if e["event_type"] == event_type) == count
