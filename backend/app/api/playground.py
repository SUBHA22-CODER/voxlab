"""Live voice playground over WebSocket.

Client -> server frames:
  {"type": "text_message", "content": "..."}
  {"type": "voice_transcript", "content": "...", "stt_ms": 180, "audio_ms": 1400}
  {"type": "stop"}

Server -> client frames:
  {"type": "session_started", "session_id": ..., "trace_id": "..."}
  {"type": "agent_message", "content": "...", "latency_ms": ..., "tool_calls": [...],
   "state": {...}, "error": null, "events": [...events recorded this turn...]}
  {"type": "session_ended", "session_id": ...}
  {"type": "error", "message": "..."}
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.adapters.base import build_adapter
from app.core.database import SessionLocal
from app.core.security import decrypt_credentials, decode_access_token
from app.engine.trace_collector import (
    EVENT_AGENT_MESSAGE,
    EVENT_AUDIO_RECEIVED,
    EVENT_ERROR,
    EVENT_SESSION_ENDED,
    EVENT_SESSION_STARTED,
    EVENT_STT_COMPLETED,
    EVENT_TOOL_CALL,
    EVENT_USER_MESSAGE,
    TraceCollector,
)
from app.models import Agent, Session, utcnow

router = APIRouter()


def _serialize_event(event: dict) -> dict:
    return {
        "sequence": event["sequence"],
        "event_type": event["event_type"],
        "timestamp": event["timestamp"].isoformat(),
        "duration_ms": event["duration_ms"],
        "payload": event["payload"],
    }


def _token_from_subprotocol(header_value: str | None) -> str | None:
    """Extract the bearer token from Sec-WebSocket-Protocol.

    The client offers ['bearer', <token>]; we select 'bearer' when accepting.
    The raw token is never echoed back to the client.
    """
    if not header_value:
        return None
    parts = [p.strip() for p in header_value.split(",")]
    if len(parts) >= 2 and parts[0].lower() == "bearer" and parts[1]:
        return parts[1]
    return None


@router.websocket("/ws/playground/{agent_id}")
async def playground_socket(websocket: WebSocket, agent_id: int):
    # Token arrives via the Sec-WebSocket-Protocol header
    # ("bearer,<token>") — browsers cannot set arbitrary WS headers, and the
    # previous ?token= query string leaked credentials into access logs.
    token = _token_from_subprotocol(websocket.headers.get("sec-websocket-protocol"))
    if token is None:
        await websocket.close(code=4401, reason="Missing token")
        return
    user_id = decode_access_token(token)
    if user_id is None:
        await websocket.close(code=4401, reason="Invalid token")
        return

    db = SessionLocal()
    try:
        agent = await db.get(Agent, agent_id)
        if agent is None or str(agent.user_id) != str(user_id):
            await websocket.close(code=4404, reason="Agent not found")
            return

        session_row = Session(
            agent_id=agent.id,
            trace_id=uuid.uuid4().hex,
            source="playground",
            status="running",
        )
        db.add(session_row)
        await db.commit()
        await db.refresh(session_row)

        collector = TraceCollector(session_row.id, session_row.trace_id)
        collector.record(
            EVENT_SESSION_STARTED, {"agent": agent.name, "mode": "playground"}
        )

        adapter = build_adapter(
            {
                "endpoint": agent.endpoint,
                "agent_type": agent.agent_type,
                "session_id": f"vx-pg{session_row.id}-{uuid.uuid4().hex[:8]}",
                "timeout_s": (agent.config or {}).get("timeout_s", 30),
            },
            decrypt_credentials(agent.auth_config_encrypted),
        )
        try:
            await adapter.connect()
        except Exception as exc:
            await websocket.accept(subprotocol="bearer")
            await websocket.send_json(
                {"type": "error", "message": f"Cannot reach agent: {exc}"[:300]}
            )
            await websocket.close(code=1011)
            return

        await websocket.accept(subprotocol="bearer")
        await websocket.send_json(
            {
                "type": "session_started",
                "session_id": session_row.id,
                "trace_id": session_row.trace_id,
            }
        )

        flushed_through = 0
        try:
            while True:
                frame = await websocket.receive_json()
                frame_type = frame.get("type")

                if frame_type == "stop":
                    break

                if frame_type not in ("text_message", "voice_transcript"):
                    await websocket.send_json(
                        {"type": "error", "message": f"Unknown frame type: {frame_type}"}
                    )
                    continue

                content = str(frame.get("content") or "")
                is_voice = frame_type == "voice_transcript"
                collector.begin_turn(len(collector._turns) + 1)

                if is_voice:
                    collector.record(
                        EVENT_AUDIO_RECEIVED,
                        {"bytes": int(frame.get("audio_bytes") or 0)},
                        duration_ms=frame.get("audio_ms"),
                    )
                    collector.record(
                        EVENT_STT_COMPLETED,
                        {"transcript": content, "provider": "browser_web_speech"},
                        duration_ms=frame.get("stt_ms"),
                    )
                collector.record(EVENT_USER_MESSAGE, {"content": content, "kind": "voice" if is_voice else "text"})

                result = await adapter.send_message(content)
                timings = result.timings or {}
                collector.stage("agent_processing", timings.get("llm_ms"), "agent turn")
                for tool_call in result.tool_calls:
                    collector.record(
                        EVENT_TOOL_CALL,
                        {"name": tool_call.get("name"), "status": tool_call.get("status", "success")},
                        duration_ms=tool_call.get("duration_ms"),
                    )
                collector.stage("tool_execution", timings.get("tool_ms"))
                e2e_ms = int(timings.get("total_ms") or 0)
                collector.stage("e2e", e2e_ms, "voice" if is_voice else "text")
                collector.record(
                    EVENT_AGENT_MESSAGE, {"content": result.reply}, duration_ms=e2e_ms
                )
                if result.error:
                    collector.record(EVENT_ERROR, {"error": result.error})
                collector.end_turn()

                new_events = [_serialize_event(e) for e in collector._events[flushed_through:]]
                flushed_through = len(collector._events)

                await websocket.send_json(
                    {
                        "type": "agent_message",
                        "content": result.reply,
                        "latency_ms": e2e_ms,
                        "tool_calls": result.tool_calls,
                        "state": result.state,
                        "error": result.error,
                        "events": new_events,
                    }
                )

                # Persist incrementally so history survives disconnects.
                for e in collector._events:
                    from app.models import Event

                    db.add(
                        Event(
                            session_id=collector.session_id,
                            sequence=e["sequence"],
                            trace_id=e["trace_id"],
                            event_type=e["event_type"],
                            timestamp=e["timestamp"],
                            duration_ms=e["duration_ms"],
                            payload=e["payload"],
                        )
                    )
                await _upsert_trace(db, collector)
                await db.commit()
        except WebSocketDisconnect:
            pass
        finally:
            collector.record(EVENT_SESSION_ENDED, {"reason": "closed"})
            session_row.status = "completed"
            session_row.finished_at = utcnow()
            for e in collector._events[flushed_through:]:
                from app.models import Event

                db.add(
                    Event(
                        session_id=collector.session_id,
                        sequence=e["sequence"],
                        trace_id=e["trace_id"],
                        event_type=e["event_type"],
                        timestamp=e["timestamp"],
                        duration_ms=e["duration_ms"],
                        payload=e["payload"],
                    )
                )
            await _upsert_trace(db, collector)
            await db.commit()
            try:
                await adapter.disconnect()
            except Exception:
                pass
            await db.close()
    except Exception:
        await db.close()
        raise


async def _upsert_trace(db, collector: TraceCollector) -> None:
    from sqlalchemy import select as _select

    from app.models import Trace

    trace = await db.scalar(_select(Trace).where(Trace.session_id == collector.session_id))
    if trace is None:
        db.add(
            Trace(
                session_id=collector.session_id,
                trace_id=collector.trace_id,
                trace_data=collector.build_trace_data(),
            )
        )
    else:
        trace.trace_data = collector.build_trace_data()
