"""Live end-to-end check against running servers.

Requires:
  - demo agent on :8100  (agent-examples/customer-support-agent)
  - backend on :8000     (backend/, seeded via `python -m app.seed`)

Run: python scripts/live_e2e.py
"""

from __future__ import annotations

import asyncio
import json
import sys

import httpx

import os

BASE = os.environ.get("VOXLAB_BASE", "http://localhost:8000")
DEMO = os.environ.get("VOXLAB_DEMO", "http://localhost:8100")
WS_BASE = os.environ.get("VOXLAB_WS_BASE", "ws://localhost:8000")
EMAIL = "demo@voxlab.dev"
PASSWORD = "demo1234"


def check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {label}" + (f" — {detail}" if detail else ""))
    return ok


async def wait_run(client: httpx.AsyncClient, headers: dict, run_id: int, timeout_s=60) -> dict:
    for _ in range(int(timeout_s / 0.4)):
        response = await client.get(f"{BASE}/api/test-runs/{run_id}", headers=headers)
        data = response.json()
        if data["status"] in ("completed", "failed", "cancelled"):
            return data
        await asyncio.sleep(0.4)
    raise TimeoutError(f"run {run_id} did not finish")


async def playground_turn(token: str, agent_id: int, message: str) -> dict:
    import websockets

    uri = f"{WS_BASE}/ws/playground/{agent_id}?token={token}"
    async with websockets.connect(uri) as ws:
        started = json.loads(await ws.recv())
        assert started["type"] == "session_started", started
        await ws.send(json.dumps({"type": "text_message", "content": message}))
        reply = json.loads(await ws.recv())
        await ws.send(json.dumps({"type": "stop"}))
        return reply


async def main() -> int:
    results: list[bool] = []

    async with httpx.AsyncClient(timeout=30) as client:
        health = await client.get(f"{BASE}/api/health")
        results.append(check("backend health", health.status_code == 200, str(health.json())))

        agent_health = await client.get(f"{DEMO}/health")
        results.append(check("demo agent health", agent_health.status_code == 200, str(agent_health.json())))

        login = await client.post(
            f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}
        )
        results.append(check("demo login", login.status_code == 200))
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        agents = (await client.get(f"{BASE}/api/agents", headers=headers)).json()
        demo_agent = next(a for a in agents if "Demo" in a["name"])
        results.append(check("demo agent registered", demo_agent["endpoint"].startswith("http://localhost:8100")))

        connect = (
            await client.post(f"{BASE}/api/agents/{demo_agent['id']}/connect", headers=headers)
        ).json()
        results.append(check("agent connection test", connect["ok"], connect["detail"][:60]))

        scenarios = (await client.get(f"{BASE}/api/scenarios", headers=headers)).json()
        results.append(check("8 builtin scenarios", len(scenarios) == 8, f"{len(scenarios)} found"))

        BROKEN = {
            "ignore_interruptions": True,
            "crash_on_tool_error": True,
            "forget_context": True,
            "hinglish_support": False,
        }
        FIXED = {
            "ignore_interruptions": False,
            "crash_on_tool_error": False,
            "forget_context": False,
            "hinglish_support": True,
        }

        # --- Broken-config benchmark ---
        await client.post(f"{DEMO}/admin/failure-config", json=BROKEN)
        await client.post(f"{DEMO}/admin/reset")
        run_response = await client.post(
            f"{BASE}/api/test-runs",
            headers=headers,
            json={"agent_id": demo_agent["id"], "scenario_ids": [s["id"] for s in scenarios]},
        )
        run_id = run_response.json()["id"]
        run = await wait_run(client, headers, run_id)
        report = run.get("report") or {}
        results.append(check("broken run completed", run["status"] == "completed", run.get("error") or ""))
        broken_score = report.get("score", 0)
        results.append(
            check("broken agent fails scenarios (deliberate failures detected)",
                  report.get("totals", {}).get("failed", 0) >= 4,
                  f"score {broken_score}, failed {report.get('totals', {}).get('failed')}")
        )

        # Trace with real timestamps for a failed session.
        failures = report.get("failures", [])
        results.append(check("failures listed with reasons", len(failures) >= 4, failures[0]["scenario_name"] if failures else ""))
        if run["sessions"]:
            session_id = run["sessions"][0]["id"]
            trace_response = await client.get(f"{BASE}/api/sessions/{session_id}/traces", headers=headers)
            trace_data = trace_response.json().get("trace_data", {})
            results.append(
                check("trace timeline collected", bool(trace_data.get("turns")), f"turns={len(trace_data.get('turns', []))}")
            )

        # --- Live playground over WebSocket ---
        reply = await playground_turn(token, demo_agent["id"], "What are your services?")
        results.append(check("playground WS turn", reply["type"] == "agent_message" and bool(reply["content"]), reply["content"][:60]))

        # --- Fix the failure config, rerun, compare ---
        await client.post(f"{DEMO}/admin/failure-config", json=FIXED)
        await client.post(f"{DEMO}/admin/reset")
        run2_response = await client.post(
            f"{BASE}/api/test-runs",
            headers=headers,
            json={"agent_id": demo_agent["id"], "scenario_ids": [s["id"] for s in scenarios]},
        )
        run2_id = run2_response.json()["id"]
        run2 = await wait_run(client, headers, run2_id)
        report2 = run2.get("report") or {}
        fixed_score = report2.get("score", 0)
        results.append(check("fixed run completed", run2["status"] == "completed", ""))
        results.append(
            check("fixed agent scores higher", fixed_score > broken_score,
                  f"{broken_score} -> {fixed_score}")
        )

        report1_row = (await client.get(f"{BASE}/api/test-runs/{run_id}/report", headers=headers)).json()
        report2_row = (await client.get(f"{BASE}/api/test-runs/{run2_id}/report", headers=headers)).json()
        comparison = (
            await client.get(
                f"{BASE}/api/reports/{report1_row['id']}/compare/{report2_row['id']}", headers=headers
            )
        ).json()
        results.append(
            check("report comparison delta positive", comparison["deltas"]["score"] > 0,
                  f"delta {comparison['deltas']['score']}")
        )

        # Restore the demo's default: the deliberately broken agent, so the
        # story always starts with "run the benchmark and watch it fail".
        await client.post(f"{DEMO}/admin/failure-config", json=BROKEN)

    print()
    passed = sum(results)
    print(f"{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
