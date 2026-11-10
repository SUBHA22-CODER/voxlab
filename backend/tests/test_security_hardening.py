# test_security_hardening.py
# VoxLab 2.5 security regression tests. Each test pins a specific hardening
# guarantee so a future change cannot silently reintroduce the weakness.

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.security import create_access_token, decode_access_token_full


@pytest.mark.asyncio
class TestDemoBypassRemoved:
    async def test_demo_login_requires_real_password(self, client, db_session):
        """demo123 (the old bypass password) must be rejected; the real seeded
        password demo1234 must still work through PBKDF2 verification."""
        from app.seed import ensure_demo_user

        await ensure_demo_user(db_session)
        old_bypass = await client.post(
            "/api/auth/login",
            json={"email": "demo@voxlab.dev", "password": "demo123"},
        )
        assert old_bypass.status_code == 401, "demo123 bypass must not authenticate"

        real = await client.post(
            "/api/auth/login",
            json={"email": "demo@voxlab.dev", "password": "demo1234"},
        )
        assert real.status_code == 200, "demo account must still work with its real password"

    async def test_login_failure_is_audited(self, client, db_session):
        from sqlalchemy import select

        from app.models.security_models import AuditEvent

        await client.post(
            "/api/auth/login", json={"email": "demo@voxlab.dev", "password": "wrong-password"}
        )
        events = (
            await db_session.scalars(
                select(AuditEvent)
                .where(AuditEvent.event_type == "login_failure")
                .order_by(AuditEvent.id.desc())
            )
        ).all()
        assert len(events) >= 1
        # The attempted password must never appear in the audit trail.
        assert "wrong-password" not in str(events[0].detail)


@pytest.mark.asyncio
class TestTokenRevocation:
    async def test_logout_revokes_token(self, client, auth_headers):
        me = await client.get("/api/auth/me", headers=auth_headers)
        assert me.status_code == 200

        out = await client.post("/api/auth/logout", headers=auth_headers)
        assert out.status_code == 200

        after = await client.get("/api/auth/me", headers=auth_headers)
        assert after.status_code == 401, "revoked token must be rejected before expiry"

    async def test_revocation_is_jti_scoped(self, client, db_session):
        """Logging out one token must not invalidate a different token for
        the same user."""
        from app.seed import ensure_demo_user

        await ensure_demo_user(db_session)
        login_a = await client.post(
            "/api/auth/login", json={"email": "demo@voxlab.dev", "password": "demo1234"}
        )
        login_b = await client.post(
            "/api/auth/login", json={"email": "demo@voxlab.dev", "password": "demo1234"}
        )
        assert login_a.status_code == 200 and login_b.status_code == 200
        token_a = login_a.json()["access_token"]
        token_b = login_b.json()["access_token"]
        assert token_a != token_b

        await client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token_a}"})

        gone = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_a}"})
        alive = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_b}"})
        assert gone.status_code == 401
        assert alive.status_code == 200

    async def test_tokens_carry_jti(self):
        token, jti = create_access_token("42")
        payload = decode_access_token_full(token)
        assert payload is not None
        assert payload.get("jti") == jti


@pytest.mark.asyncio
class TestRateLimiting:
    async def test_audio_transcribe_rate_limited(self, client, auth_headers, monkeypatch):
        """The expensive transcription endpoint enforces its own budget."""
        import io
        import wave

        import numpy as np

        from app.core import rate_limit

        # Stub engine: the rate limit, not the model, is under test.
        import app.api.v1.audio as audio_mod

        async def fake_get_engine(engine_id: str = "whisper_local"):
            from tests.test_api_v1_audio import StubAPIEngine

            return StubAPIEngine()

        monkeypatch.setattr(audio_mod, "get_engine", fake_get_engine)

        def wav_bytes() -> bytes:
            buf = io.BytesIO()
            with wave.open(buf, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(16000)
                t = np.arange(1600) / 16000
                w.writeframes((0.3 * np.sin(2 * np.pi * 300 * t) * 32767).astype("<i2").tobytes())
            return buf.getvalue()

        rate_limit._hits.clear()
        original = rate_limit.TEST_OVERRIDE_LIMIT
        rate_limit.TEST_OVERRIDE_LIMIT = 3
        try:
            statuses = []
            for _ in range(5):
                response = await client.post(
                    "/api/v1/audio/transcribe",
                    headers=auth_headers,
                    files={"file": ("clip.wav", wav_bytes(), "audio/wav")},
                )
                statuses.append(response.status_code)
            assert statuses[:3] == [200, 200, 200], f"first three should pass: {statuses}"
            assert statuses[3] == 429, f"fourth must be rate limited: {statuses}"
        finally:
            rate_limit.TEST_OVERRIDE_LIMIT = original
            rate_limit._hits.clear()


@pytest.mark.asyncio
class TestAuditEndpoints:
    async def test_audit_lists_only_own_events(self, client, auth_headers, user, db_session):
        from sqlalchemy import select

        from app.models.security_models import AuditEvent
        from app.models import User as UserRow

        other = UserRow(email="other-audit@voxlab.dev", password_hash="x")
        db_session.add(other)
        await db_session.flush()
        db_session.add(AuditEvent(user_id=other.id, event_type="login_success"))
        db_session.add(AuditEvent(user_id=user.id, event_type="login_success"))
        await db_session.commit()

        response = await client.get("/api/v1/security/audit", headers=auth_headers)
        assert response.status_code == 200
        events = response.json()
        assert len(events) >= 1
        assert all(e["event_type"] == "login_success" for e in events)
        # cross-user events must be absent (their user id differs)
        mine_ids = {e["id"] for e in events}
        all_rows = (await db_session.scalars(select(AuditEvent))).all()
        other_rows = [r for r in all_rows if r.user_id == other.id]
        assert not (mine_ids & {r.id for r in other_rows})

    async def test_security_health_reports_subsystems(self, client, auth_headers):
        response = await client.get("/api/v1/security/health", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] in {"ok", "degraded"}
        assert body["auth"]["revocation"] == "enabled"
        assert body["auth"]["demo_bypass_removed"] is True
        assert body["retention"]["audio_retention_days"] >= 0
        assert isinstance(body["engines"], list)


@pytest.mark.asyncio
class TestDemoUserSelfHealing:
    async def test_legacy_demo_password_is_healed(self, db_session):
        """A database that still carries a legacy demo hash (pre-2.0
        'demo123') is healed to the documented credential at startup."""
        from app.core.security import hash_password, verify_password
        from app.models import User as UserRow
        from app.seed import DEMO_EMAIL, DEMO_PASSWORD, ensure_demo_user

        # Simulate the legacy state: wrong hash on the demo account.
        user = await db_session.scalar(
            select(UserRow).where(UserRow.email == DEMO_EMAIL)
        )
        if user is None:
            user = UserRow(email=DEMO_EMAIL, password_hash=hash_password("legacy"))
            db_session.add(user)
        else:
            user.password_hash = hash_password("legacy-password")
        await db_session.commit()

        healed = await ensure_demo_user(db_session)
        assert verify_password(DEMO_PASSWORD, healed.password_hash), (
            "ensure_demo_user must reset a non-canonical demo hash"
        )
