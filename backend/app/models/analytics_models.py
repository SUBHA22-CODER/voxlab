# analytics_models.py
# VoxLab 2.5: model drift snapshots over fixed benchmark datasets.

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models import utcnow


class AudioDriftSnapshot(Base):
    """One evaluation of a FIXED benchmark dataset by one engine/model.

    Snapshots are immutable; drift is computed by comparing two of them.
    results JSON: [{case_id, wer, cer, rtf, hypothesis, error}]
    """

    __tablename__ = "audio_drift_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    dataset_name: Mapped[str] = mapped_column(String(128), index=True)
    engine: Mapped[str] = mapped_column(String(64), index=True)
    model_version: Mapped[str] = mapped_column(String(128), default="")
    case_count: Mapped[int] = mapped_column(Integer, default=0)
    mean_wer: Mapped[float] = mapped_column(Float, default=0.0)
    mean_cer: Mapped[float] = mapped_column(Float, default=0.0)
    mean_rtf: Mapped[float] = mapped_column(Float, default=0.0)
    results: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
