# audit.py
# Best-effort security audit trail. An audit write failure is logged and
# swallowed deliberately: the audit trail must never break the primary
# operation it is observing (auth, deletion, run starts).

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security_models import AuditEvent

logger = logging.getLogger(__name__)


async def record_event(
    db: AsyncSession,
    *,
    event_type: str,
    user_id: int | None = None,
    source_ip: str | None = None,
    detail: dict[str, Any] | None = None,
    note: str | None = None,
    commit: bool = False,
) -> None:
    """Append one audit event. Caller owns the transaction unless commit=True."""
    try:
        db.add(
            AuditEvent(
                user_id=user_id,
                event_type=event_type,
                source_ip=source_ip,
                detail=detail or {},
                note=note,
            )
        )
        if commit:
            await db.commit()
    except Exception as exc:  # noqa: BLE001 - audit must never break the caller
        logger.warning("audit write failed for %s: %s", event_type, exc)
        if commit:
            try:
                await db.rollback()
            except Exception:  # noqa: BLE001
                pass
