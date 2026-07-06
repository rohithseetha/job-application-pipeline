"""Shared helpers used by every fetcher/*.py module."""

from __future__ import annotations

from sqlalchemy.orm import Session

from common.schema import NormalizedPosting
from db.models import Job


def upsert_postings(session: Session, postings: list[NormalizedPosting]) -> int:
    """Insert new postings, leave existing ones (and their scoring/status) untouched.

    Returns the number of newly inserted rows.
    """
    existing_ids = {
        row.id
        for row in session.query(Job.id).filter(
            Job.id.in_([p.id for p in postings])
        )
    }

    inserted = 0
    for posting in postings:
        if posting.id in existing_ids:
            continue
        session.add(
            Job(
                id=posting.id,
                source=posting.source,
                title=posting.title,
                company=posting.company,
                location=posting.location,
                description=posting.description,
                source_url=posting.source_url,
                fetched_at=posting.fetched_at,
            )
        )
        inserted += 1
    return inserted
