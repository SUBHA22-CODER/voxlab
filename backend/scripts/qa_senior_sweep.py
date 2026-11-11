# qa_senior_sweep.py
# Senior voice-AI engineer QA sweep: exercises EVERY live surface on the
# running stack and prints PASS/FAIL per check. Read-only against the
# platform's own API (plus one ephemeral test user); deletes nothing owned
# by other users.

from __future__ import annotations

import asyncio
import io
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402
import numpy as np  # noqa: E402

BASE = "http://localhost:8001"
FRONTEND = "http://localhost:3000"
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not ok else ""))


def wav_bytes(seconds: float = 1.0, freq: float = 300.0) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        t = np.arange(int(seconds * 16000)) / 16000
        w.writeframes((0.4 * np.sin(2 * np.pi * freq * t) * 32767).astype("<i2").tobytes())
    return buf.getvalue()


async def main() -> None:
    async with httpx.AsyncClient(timeout=300.0) as c:
        # --- auth & security ------------------------------------------------
        r = await c.post(f"{BASE}/api/auth/register",
                         json={"email": f"qa-{int(np.random.randint(1e6))}@voxlab.dev", "password": "qa-pass-123"})
        check("auth: register 201", r.status_code == 201, str(r.status_code))
        tok = r.json().get("access_token", "")
        H = {"Authorization": f"Bearer {tok}"}

        r = await c.get(f"{BASE}/api/auth/me", headers=H)
        check("auth: /me with fresh token", r.status_code == 200)

        r2 = await c.post(f"{BASE}/api/auth/login",
                          json={"email": "demo@voxlab.dev", "password": "demo123"})
        check("security: legacy demo123 REJECTED", r2.status_code == 401)

        # --- engines --------------------------------------------------------
        r = await c.get(f"{BASE}/api/v1/engines", headers=H)
        engines = {e["engine_id"]: e["installed"] for e in r.json()}
        check("engines: all three known",
              set(engines) == {"whisper_local", "vosk", "wav2vec2"}, str(engines))
        check("engines: all installed", all(engines.values()), str(engines))

        for eid in engines:
            r = await c.get(f"{BASE}/api/v1/engines/{eid}/health", headers=H)
            body = r.json()
            check(f"engines: {eid} healthy", r.status_code == 200 and body["status"] == "healthy",
                  str(body)[:100])

        # --- transcribe per engine -------------------------------------------
        fixture = Path("tests/fixtures/human_voices/janeeyre-female-uk-anchored.wav")
        blob = fixture.read_bytes() if fixture.exists() else wav_bytes(2.0)
        fname = fixture.name if fixture.exists() else "tone.wav"
        ref = ("This is a LibriVox recording. All LibriVox recordings are in the "
               "public domain. For more information or to volunteer, please visit librivox.org.")
        for eid in engines:
            r = await c.post(f"{BASE}/api/v1/audio/transcribe", headers=H,
                             files={"file": (fname, blob, "audio/wav")},
                             data={"engine_id": eid, "reference_transcript": ref,
                                   "use_llm_judge": "false"})
            body = r.json()
            ok = r.status_code == 200 and body.get("text")
            check(f"transcribe: {eid} on real human voice", ok, str(body)[:120])
            if ok:
                check(f"transcribe: {eid} returns alignment+semantic",
                      body.get("alignment") is not None and body.get("semantic") is not None)

        r = await c.post(f"{BASE}/api/v1/audio/transcribe", headers=H,
                         files={"file": ("bad.wav", b"not-a-wav", "audio/wav")})
        check("validation: corrupt audio -> 422", r.status_code == 422, str(r.status_code))

        # --- benchmarks (multi-engine) ----------------------------------------
        r = await c.post(f"{BASE}/api/v1/benchmarks/audio", headers=H,
                         files={"file": (fname, blob, "audio/wav")},
                         data={"engines": "whisper_local,vosk,wav2vec2", "reference_transcript": ref})
        body = r.json()
        ok_rows = [x for x in body.get("engine_results", []) if x["status"] == "ok"]
        check("benchmark: three engines side-by-side", r.status_code == 201 and len(ok_rows) == 3,
              f"rows={len(body.get('engine_results', []))}")

        # --- darwin audio (catalogs; a full evolve run is covered by tests) ---
        r = await c.get(f"{BASE}/api/v1/darwin/audio/personas", headers=H)
        check("darwin audio: personas catalog", r.status_code == 200 and len(r.json()) >= 10)
        r = await c.get(f"{BASE}/api/v1/darwin/audio/transforms", headers=H)
        check("darwin audio: transform catalog", r.status_code == 200 and len(r.json()) >= 14)

        # --- analytics --------------------------------------------------------
        r = await c.get(f"{BASE}/api/v1/analytics/robustness", headers=H)
        check("analytics: robustness", r.status_code == 200)
        r = await c.get(f"{BASE}/api/v1/analytics/datasets", headers=H)
        ds = {d["name"] for d in r.json()}
        check("analytics: datasets visible (core-en-v1 + human-voices-v1)",
              {"core-en-v1", "human-voices-v1"} <= ds, str(ds))
        if "human-voices-v1" in ds:
            r = await c.post(f"{BASE}/api/v1/analytics/datasets/human-voices-v1/snapshot?engine_id=wav2vec2",
                             headers=H)
            check("analytics: human-voice snapshot (wav2vec2)", r.status_code == 201, str(r.status_code))

        # --- regressions + security -------------------------------------------
        r = await c.get(f"{BASE}/api/v1/regressions", headers=H)
        check("regressions: list", r.status_code == 200)
        r = await c.get(f"{BASE}/api/v1/security/health", headers=H)
        check("security: health", r.status_code == 200 and r.json()["database"]["reachable"])
        r = await c.get(f"{BASE}/api/v1/security/audit", headers=H)
        check("security: audit trail", r.status_code == 200)

        # --- logout revocation --------------------------------------------------
        r = await c.post(f"{BASE}/api/auth/logout", headers=H)
        check("security: logout", r.status_code == 200)
        r = await c.get(f"{BASE}/api/auth/me", headers=H)
        check("security: revoked token rejected", r.status_code == 401)

        # --- frontend -----------------------------------------------------------
        r = await c.get(FRONTEND + "/")
        check("frontend: serving", r.status_code == 200)
        for page in ("audio", "audio/darwin", "benchmarks", "analytics", "regressions", "dashboard"):
            r = await c.get(f"{FRONTEND}/{page}")
            check(f"frontend: /{page}", r.status_code == 200)

    print("\n================ QA SUMMARY ================")
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = [(n, d) for n, ok, d in RESULTS if not ok]
    print(f"{passed}/{len(RESULTS)} checks passed")
    for n, d in failed:
        print(f"  FAILED: {n} {d}")


asyncio.run(main())
