# security_models.py
# VoxLab 2.5 security models: JWT revocation registry and the audit trail.

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models import utcnow


class RevokedToken(Base):
    """Revoked JWTs (by jti). Rows are kept until the token's exp; a sweep
    removes expired entries so the table stays bounded."""

    __tablename__ = "revoked_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AuditEvent(Base):
    """Security-relevant event trail: logins (success/failure), registrations,
    logouts, agent lifecycle, deletions. Written best-effort — an audit
    failure must never break the primary operation."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    # login_success | login_failure | register | logout | token_revoked |
    # agent_registered | agent_deleted | case_deleted | run_started | ...
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
