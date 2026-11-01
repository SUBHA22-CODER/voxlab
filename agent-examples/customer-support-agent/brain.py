"""The demo agent's conversational brain.

Scripted by default (deterministic, fast, works offline). Set
LLM_DEMO_MODE=llm + an OpenAI-compatible key to compose replies with an LLM
instead — failure switches are applied as system-prompt directives.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

import orders
from failure_config import get as failure_config

ORDER_ID_RE = re.compile(r"\bORD-\d{3,6}\b", re.IGNORECASE)

HINGLISH_RE = re.compile(
    r"\b(mera|kab|kya|hai|kitna|chahiye|nahi|nahin|aayega|karna|bhai|matlab|achha|theek)\b",
    re.IGNORECASE,
)

FAQ: list[tuple[tuple[str, ...], str]] = [
    (
        ("service", "what do you do", "what can you do", "capabilit"),
        "We offer 24/7 automated customer support across voice, chat, and email — "
        "including order tracking, cancellations, returns, and live escalations to human agents.",
    ),
    (
        ("pricing", "price", "cost", "how much", "plan"),
        "Our plans start at $19/month for the Starter tier, $49/month for Pro with "
        "priority routing and analytics, and custom Enterprise pricing for high-volume teams.",
    ),
    (
        ("hour", "open", "timing", "when are you available"),
        "The automated assistant is available 24/7. Human support agents are online "
        "from 9 AM to 9 PM, Monday through Saturday.",
    ),
    (
        ("return", "refund", "money back"),
        "You can return any item within 30 days of delivery for a full refund. "
        "Refunds are processed within 3-5 business days after we receive the item.",
    ),
]


@dataclass
class SessionState:
    history: list[dict] = field(default_factory=list)
    order_id: str | None = None
    escalated: bool = False
    cancelled: bool = False
    turns: int = 0
    pending_topic: str | None = None


def _find_faq(message: str) -> str | None:
    low = message.lower()
    for keywords, answer in FAQ:
        if any(k in low for k in keywords):
            return answer
    return None


def extract_order_id(message: str) -> str | None:
    match = ORDER_ID_RE.search(message)
    return match.group(0).upper() if match else None


def looks_hinglish(message: str) -> bool:
    return len(HINGLISH_RE.findall(message)) >= 2


class Brain:
    """Produces one conversational turn. Returns (reply, tool_calls, error)."""

    def __init__(self) -> None:
        self.use_llm = os.environ.get("LLM_DEMO_MODE") == "llm" and bool(
            os.environ.get("LLM_API_KEY")
        )
        self._llm = None
        if self.use_llm:
            from llm import LLMClient

            self._llm = LLMClient()

    async def respond(
        self, session: SessionState, message: str, metadata: dict
    ) -> tuple[str, list[orders.ToolCall], str | None]:
        config = failure_config()
        session.turns += 1

        signal = metadata.get("signal")
        if signal == "ping":
            return "pong", [], None
        if signal == "silence":
            return (
                "Are you still there? Take your time — I can help you check an order, "
                "cancel a purchase, or answer questions about our services.",
                [],
                None,
            )

        # Deliberate failure #1: plows on with the previous topic.
        if metadata.get("interrupt") and config["ignore_interruptions"]:
            topic = session.pending_topic or "our services"
            reply = (
                f"...so, as I was saying about {topic}: we support order tracking, "
                "cancellations, and returns around the clock."
            )
            session.history.append({"role": "user", "content": message})
            session.history.append({"role": "agent", "content": reply})
            return reply, [], None

        inject_fail = bool((metadata.get("inject") or {}).get("tool_failure"))

        # Deliberate failure #4: pretends not to know context it has.
        if config["forget_context"] and extract_order_id(message) is None:
            session.order_id = None

        new_order_id = extract_order_id(message)
        if new_order_id:
            session.order_id = new_order_id

        if self._llm is not None:
            return await self._respond_llm(session, message, inject_fail, config)
        return await self._respond_scripted(session, message, metadata, inject_fail, config)

    # --- scripted mode (default) ---

    async def _respond_scripted(
        self,
        session: SessionState,
        message: str,
        metadata: dict,
        inject_fail: bool,
        config: dict,
    ) -> tuple[str, list[orders.ToolCall], str | None]:
        low = message.lower()
        interrupting = bool(metadata.get("interrupt"))

        # Deliberate failure #3: refuses Hinglish.
        if looks_hinglish(message) and not config["hinglish_support"]:
            return (
                "I'm sorry, I can only understand English. Could you please repeat that in English?",
                [],
                None,
            )

        wants_human = any(k in low for k in ("human", "real person", "manager", "escalate", "speak to someone"))
        wants_cancel = "cancel" in low
        wants_status = any(
            k in low
            for k in (
                "status", "where is", "track", "check order", "my order",
                "arrive", "delivery", "order id", "kab aayega", "aayega",
            )
        )

        if wants_human:
            return await self._run_tool(
                session,
                orders.escalate_to_human,
                (low[:120],),
                fail=inject_fail,
                success_reply=(
                    "I've escalated this to a human support agent. They'll join in about "
                    "four minutes, and I've shared our conversation so you won't repeat yourself."
                ),
                on_success=lambda: setattr(session, "escalated", True),
            )

        if wants_cancel:
            if not session.order_id:
                session.pending_topic = "cancellations"
                return (
                    "Sure, I can help with a cancellation. Could you share your order ID "
                    "(it looks like ORD-1234)?",
                    [],
                    None,
                )
            return await self._run_tool(
                session,
                orders.cancel_order,
                (session.order_id,),
                fail=inject_fail,
                success_reply_builder=lambda result: (
                    f"Done — order {session.order_id} is cancelled. Your confirmation code is "
                    f"{result['confirmation']} and the refund lands in {result['refund_days']}."
                ),
                on_success=lambda: setattr(session, "cancelled", True),
            )

        if wants_status:
            if not session.order_id:
                session.pending_topic = "order status"
                return (
                    "I can check that for you. Which order is it — could you share the order ID?",
                    [],
                    None,
                )
            return await self._run_tool(
                session,
                orders.check_order_status,
                (session.order_id,),
                fail=inject_fail,
                success_reply_builder=lambda result: _status_reply(session.order_id, result),
            )

        faq_answer = _find_faq(message)
        if faq_answer:
            session.pending_topic = (
                "our services" if ("service" in low or "capabilit" in low) else "pricing"
            )
            reply = faq_answer
            if interrupting:
                reply = "Of course — " + reply[0].lower() + reply[1:]
            session.history.append({"role": "user", "content": message})
            session.history.append({"role": "agent", "content": reply})
            return reply, [], None

        if any(k in low for k in ("hi", "hello", "hey", "good morning", "good evening")):
            reply = (
                "Hi! I'm the customer support assistant. I can check order status, cancel an "
                "order, or answer questions about our services and pricing."
            )
            session.pending_topic = "our services"
            session.history.append({"role": "user", "content": message})
            session.history.append({"role": "agent", "content": reply})
            return reply, [], None

        reply = "Sorry, I didn't quite catch that. Could you share your order ID, or ask about our services, pricing, returns, or hours?"
        if session.order_id:
            reply = (
                f"I have order {session.order_id} on file. You can ask for its status, cancel it, "
                "or ask about our services, pricing, returns, or hours."
            )
        session.history.append({"role": "user", "content": message})
        session.history.append({"role": "agent", "content": reply})
        return reply, [], None

    async def _run_tool(
        self,
        session: SessionState,
        tool,
        args: tuple,
        fail: bool,
        success_reply: str | None = None,
        success_reply_builder=None,
        on_success=None,
    ) -> tuple[str, list[orders.ToolCall], str | None]:
        config = failure_config()
        try:
            call = await orders.call_with_failure(tool, *args, fail=fail)
        except orders.MockAPIError:
            if config["crash_on_tool_error"]:
                # Deliberate failure #2: agent crashes instead of recovering.
                return "", [], "mock_api_failure"
            reply = (
                "I'm sorry — I'm having trouble reaching our order system right now. "
                "Could you try again in a moment, or would you like me to bring in a human agent?"
            )
            session.history.append({"role": "user", "content": "(tool failure)"})
            session.history.append({"role": "agent", "content": reply})
            return reply, [], None

        if call.status == "error":
            result = call.result if isinstance(call.result, dict) else {}
            if result.get("error") == "order_not_found":
                reply = (
                    f"I couldn't find an order with ID {call.args.get('order_id')}. "
                    "Could you double-check it? It looks like ORD-1234."
                )
            elif result.get("error") == "not_cancellable":
                reply = (
                    f"I couldn't cancel order {call.args.get('order_id')} because it has already "
                    "shipped. Once it arrives, you can return it within 30 days for a full refund."
                )
            else:
                reply = "Something went wrong on my side. Could you try that again?"
            session.history.append({"role": "user", "content": json.dumps(call.args)})
            session.history.append({"role": "agent", "content": reply})
            return reply, [call], None

        if success_reply_builder is not None:
            reply = success_reply_builder(call.result)
        else:
            reply = success_reply or "Done."
        if on_success is not None:
            on_success()
        session.history.append({"role": "user", "content": json.dumps(call.args)})
        session.history.append({"role": "agent", "content": reply})
        return reply, [call], None

    # --- optional LLM mode ---

    async def _respond_llm(
        self, session: SessionState, message: str, inject_fail: bool, config: dict
    ) -> tuple[str, list[orders.ToolCall], str | None]:
        assert self._llm is not None
        directives = []
        if config["ignore_interruptions"]:
            directives.append(
                "When interrupted, continue your previous topic and do not answer the interruption."
            )
        if config["crash_on_tool_error"] and inject_fail:
            directives.append("The user's message refers to a failing tool call: reply with an empty string.")
        if config["forget_context"]:
            directives.append("Never use previously known order IDs; always ask for the order ID again.")
        if not config["hinglish_support"]:
            directives.append("If the user writes in Hindi or Hinglish, reply that you only understand English.")

        context = (
            "You are a customer support voice agent for an electronics store. Answer in one or "
            "two short sentences. Known order ID on file: "
            f"{session.order_id or 'none'}. Behavior directives: {' '.join(directives) or 'none'}."
        )
        reply = await self._llm.complete(context, session.history, message)
        session.history.append({"role": "user", "content": message})
        session.history.append({"role": "agent", "content": reply})
        return reply, [], None


def _status_reply(order_id: str | None, result: dict) -> str:
    status = result.get("status", "unknown")
    if result.get("eta") in (None, "unknown"):
        eta_part = ", the carrier hasn't given a new delivery date yet"
    else:
        eta_part = f", expected to arrive by {result['eta']}"
    note = f" — note: {result['note']}" if result.get("note") else ""
    return f"Your order {order_id} is currently {status}{eta_part}{note}. Anything else I can help with?"
