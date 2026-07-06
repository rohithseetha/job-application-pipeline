"""Apply scoring to every job still in status='fetched'."""

from __future__ import annotations

from db.models import Job
from db.session import get_session
from scorer.rules import score_job


def score_pending_jobs() -> int:
    with get_session() as session:
        pending = session.query(Job).filter(Job.status == "fetched").all()
        for job in pending:
            result = score_job(job.title, job.description)
            job.requires_citizenship = result.requires_citizenship
            job.requires_clearance = result.requires_clearance
            job.tech_match_score = result.tech_match_score
            job.status = result.status
        return len(pending)


def main() -> None:
    scored = score_pending_jobs()
    print(f"Scored {scored} job(s).")


if __name__ == "__main__":
    main()
