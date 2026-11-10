"""VoxLab 2.5 security & system-health APIs (owner-scoped)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.core import rate_limit
from app.models import User
from app.models.security_models import AuditEvent, RevokedToken
from app.speech.registry import engine_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/security", tags=["security-v1"])


@router.get("/audit")
async def list_audit_events(
    limit: int = Query(default=50, ge=1, le=200),
    event_type: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The requesting user's own audit trail (never other users')."""
    query = select(AuditEvent).where(AuditEvent.user_id == user.id)
    if event_type:
        query = query.where(AuditEvent.event_type == event_type)
    rows = (
        await db.scalars(query.order_by(AuditEvent.id.desc()).limit(limit))
    ).all()
    return [
        {
            "id": row.id,
            "event_type": row.event_type,
            "detail": row.detail,
            "source_ip": row.source_ip,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get("/health")
async def security_health(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """System health overview: engines, auth subsystem, retention, DB."""
    settings = get_settings()
    db_ok = True
    revoked_count = -1
    try:
        revoked_count = await db.scalar(select(func.count()).select_from(RevokedToken)) or 0
    except Exception:  # noqa: BLE001 - health must report, not raise
        db_ok = False

    audit_count = -1
    if db_ok:
        try:
            audit_count = (
                await db.scalar(
                    select(func.count()).select_from(AuditEvent).where(
                        AuditEvent.user_id == user.id
                    )
                )
                or 0
            )
        except Exception:  # noqa: BLE001
            pass

    engines = engine_registry.describe_all()
    return {
        "status": "ok" if db_ok else "degraded",
        "checked_at": datetime.now(UTC).isoformat(),
        "database": {"reachable": db_ok, "revoked_tokens": revoked_count},
        "auth": {
            "token_type": "bearer JWT (HS256, jti-tracked)",
            "revocation": "enabled",
            "demo_bypass_removed": True,
            "rate_limit_rules": [
                {"path": prefix, "window_seconds": window, "max_requests": limit}
                for prefix, window, limit in rate_limit.RULES
            ],
        },
        "retention": {
            "audio_retention_days": settings.audio_retention_days,
            "storage_dir": settings.audio_storage_dir,
        },
        "engines": [
            {"engine_id": e["engine_id"], "installed": e["installed"]}
            for e in engines
        ],
        "own_audit_events": audit_count,
    }
