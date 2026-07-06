"""SQLAlchemy models for the jobs table.

Status lifecycle (plain string column, values enforced in application code):
    fetched  -> scorer has not yet run
    skip     -> scorer flagged a hard disqualifier (citizenship/clearance)
    scored   -> scorer ran, tech_match_score set, awaiting human review
    reviewed -> human approved the drafted resume diff / cover letter
    rejected -> human skipped this job during review
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    requires_citizenship: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_clearance: Mapped[bool] = mapped_column(Boolean, default=False)
    tech_match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String, default="fetched")
