"""Event collection and pipeline trace building (spec Module D)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, Trace

# Standard internal event types (VoxLab event format).
EVENT_SESSION_STARTED = "session_started"
EVENT_SESSION_ENDED = "session_ended"
EVENT_USER_MESSAGE = "user_message"
EVENT_AGENT_MESSAGE = "agent_message"
EVENT_AGENT_PROCESSING = "agent_processing"
EVENT_TOOL_CALL = "tool_call"
EVENT_INTERRUPTION = "interruption"
EVENT_TOOL_FAILURE_INJECTED = "tool_failure_injected"
EVENT_SILENCE = "silence"
EVENT_ERROR = "error"
EVENT_AUDIO_RECEIVED = "audio_received"
EVENT_STT_COMPLETED = "stt_completed"
EVENT_TTS_COMPLETED = "tts_completed"


def utcnow():
    return datetime.now(timezone.utc)


class TraceCollector:
    """Buffers events for one session, then persists them as rows + a trace."""

    def __init__(self, session_id: int, trace_id: str):
        self.session_id = session_id
        self.trace_id = trace_id
        self._events: list[dict] = []
        self._turns: list[dict] = []
        self._current_turn: dict | None = None

    # -- raw events --

    def record(
        self,
        event_type: str,
        payload: dict | None = None,
        duration_ms: int | None = None,
    ) -> dict:
        event = {
            "sequence": len(self._events),
            "trace_id": self.trace_id,
            "event_type": event_type,
            "timestamp": utcnow(),
            "duration_ms": duration_ms,
            "payload": payload or {},
        }
        self._events.append(event)
        return event

    # -- per-turn pipeline stages --

    def begin_turn(self, turn_index: int) -> None:
        self._current_turn = {"turn": turn_index, "stages": []}

    def stage(self, name: str, duration_ms: int | None, detail: str | None = None) -> None:
        if self._current_turn is None or duration_ms is None:
            return
        self._current_turn["stages"].append(
            {"stage": name, "duration_ms": int(duration_ms), "detail": detail}
        )

    def end_turn(self) -> None:
        if self._current_turn is not None:
            self._turns.append(self._current_turn)
            self._current_turn = None

    # -- persistence --

    def build_trace_data(self) -> dict:
        stage_totals: dict[str, int] = {}
        for turn in self._turns:
            for st in turn["stages"]:
                stage_totals[st["stage"]] = stage_totals.get(st["stage"], 0) + st["duration_ms"]
        e2e_total = sum(
            st["duration_ms"]
            for turn in self._turns
            for st in turn["stages"]
            if st["stage"] == "e2e"
        )
        return {
            "turns": self._turns,
            "summary": {
                "stage_totals_ms": stage_totals,
                "e2e_total_ms": e2e_total,
                "turn_count": len(self._turns),
                # Stage timings can overlap in streaming systems; the total
                # here is the sum of measured per-turn wall-clock turns.
                "illustrative": True,
            },
        }

    async def flush(self, db: AsyncSession) -> None:
        for e in self._events:
            db.add(
                Event(
                    session_id=self.session_id,
                    sequence=e["sequence"],
                    trace_id=e["trace_id"],
                    event_type=e["event_type"],
                    timestamp=e["timestamp"],
                    duration_ms=e["duration_ms"],
                    payload=e["payload"],
                )
            )
        db.add(
            Trace(
                session_id=self.session_id,
                trace_id=self.trace_id,
                trace_data=self.build_trace_data(),
            )
        )
        await db.flush()
