"""Normalized posting schema shared by every fetcher module."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class NormalizedPosting(BaseModel):
    """Common shape every fetcher/*.py must produce, regardless of source."""

    id: str  # f"{source}:{native_id}" — globally unique across sources
    source: str
    title: str
    company: str
    location: str | None = None
    description: str
    source_url: str
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
