"""Mock order repository — the demo agent's fake backend API.

Simulated network latency + a togglable failure mode so scenarios can
observe how the agent handles API errors.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

ORDERS: dict[str, dict] = {
    "ORD-1001": {
        "status": "shipped",
        "eta": "November 4",
        "items": "Wireless noise-cancelling headphones",
        "cancellable": False,
    },
    "ORD-1002": {
        "status": "processing",
        "eta": "November 6",
        "items": "Mechanical keyboard",
        "cancellable": True,
    },
    "ORD-1003": {
        "status": "delayed",
        "eta": "unknown",
        "items": "USB-C docking station",
        "cancellable": True,
        "note": "carrier delay in your region",
    },
}


class MockAPIError(Exception):
    """Simulated backend failure (HTTP 500)."""


@dataclass
class ToolCall:
    name: str
    args: dict = field(default_factory=dict)
    result: dict | str = ""
    status: str = "success"
    duration_ms: int = 0


async def _simulate_latency() -> None:
    await asyncio.sleep(0.04)


async def check_order_status(order_id: str) -> ToolCall:
    started = time.perf_counter()
    await _simulate_latency()
    if order_id not in ORDERS:
        return ToolCall(
            "check_order_status",
            {"order_id": order_id},
            {"error": "order_not_found"},
            status="error",
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
    order = ORDERS[order_id]
    return ToolCall(
        "check_order_status",
        {"order_id": order_id},
        {k: order[k] for k in ("status", "eta", "items") if k in order},
        duration_ms=int((time.perf_counter() - started) * 1000),
    )


async def cancel_order(order_id: str) -> ToolCall:
    started = time.perf_counter()
    await _simulate_latency()
    order = ORDERS.get(order_id)
    if order is None:
        return ToolCall(
            "cancel_order",
            {"order_id": order_id},
            {"error": "order_not_found"},
            status="error",
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
    if not order.get("cancellable"):
        return ToolCall(
            "cancel_order",
            {"order_id": order_id},
            {"error": "not_cancellable", "reason": "order already shipped"},
            status="error",
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
    order["status"] = "cancelled"
    return ToolCall(
        "cancel_order",
        {"order_id": order_id},
        {"cancelled": True, "confirmation": f"CXL-{order_id[-4:]}", "refund_days": "3-5 business days"},
        duration_ms=int((time.perf_counter() - started) * 1000),
    )


async def escalate_to_human(reason: str) -> ToolCall:
    started = time.perf_counter()
    await _simulate_latency()
    return ToolCall(
        "escalate_to_human",
        {"reason": reason[:120]},
        {"escalated": True, "queue": "human-support", "wait_minutes": 4},
        duration_ms=int((time.perf_counter() - started) * 1000),
    )


async def call_with_failure(tool, *args, fail: bool = False) -> ToolCall:
    """Run a tool; when `fail` is set the simulated backend returns a 500."""
    if fail:
        await _simulate_latency()
        raise MockAPIError("simulated backend failure (HTTP 500)")
    return await tool(*args)
