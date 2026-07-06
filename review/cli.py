"""CLI: review drafted applications for each 'scored' job.

For every job with status='scored', drafts a resume + cover letter (as both
LaTeX/text sources and compiled PDFs, via review/actions.py), shows the
summary, and lets you approve, edit, or skip. Approved/edited drafts are
logged to application_tracker.csv; the job's DB status updates to 'reviewed'
or 'rejected'. Nothing is ever sent automatically.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from db.models import Job
from db.session import get_session
from review.actions import draft_dir_for, generate_draft, record_decision, update_cover_letter


def _edit_text(text: str) -> str:
    editor = os.environ.get("EDITOR", "vi")
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
        f.write(text)
        path = f.name
    subprocess.run([editor, path], check=True)
    edited = Path(path).read_text()
    Path(path).unlink()
    return edited


def _prompt_choice(prompt: str, choices: str) -> str:
    while True:
        answer = input(f"{prompt} [{choices}] ").strip().lower()
        if answer in choices:
            return answer


def review_job(job: Job) -> None:
    print(f"\n{'=' * 70}\n{job.title} @ {job.company}  (score: {job.tech_match_score})\n{job.source_url}\n{'=' * 70}")
    print("Drafting resume + cover letter + PDFs...")
    draft = generate_draft(job)

    if draft.get("skip_recommended"):
        print("\nModel recommends SKIPPING this job:")
        for note in draft.get("gap_notes", []):
            print(f"  - {note}")
        if _prompt_choice("Reject this job?", "yn") == "y":
            record_decision(job.id, "rejected", "skip_recommended by model")
            print(f"-> {job.id}: rejected")
        else:
            print(f"-> {job.id}: left as 'scored' (no draft generated) for manual follow-up")
        return

    if draft["pdf_error"]:
        print(f"\n!! PDF compilation issue: {draft['pdf_error']}")
        print("   (.tex/.txt sources were still saved — check drafts/ for details)")

    print("\n--- Resume diff (summary) ---")
    for edit in draft["resume_diff"]:
        print(f"[{edit['section']}] {edit['change']}\n    why: {edit['reason']}")
    print("\n--- Cover letter ---")
    print(draft["cover_letter"])
    if draft["gap_notes"]:
        print("\n--- Gap notes ---")
        for note in draft["gap_notes"]:
            print(f"  - {note}")

    job_dir = draft_dir_for(job.id)
    print(f"\nPDFs: {job_dir / 'resume.pdf'}, {job_dir / 'cover_letter.pdf'}")

    choice = _prompt_choice("\nApprove (a) / Edit (e) / Skip (s)?", "aes")
    if choice == "a":
        record_decision(job.id, "reviewed", "approved as drafted")
    elif choice == "e":
        edited = _edit_text(draft["cover_letter"])
        update_cover_letter(job, edited)
        record_decision(job.id, "reviewed", "approved with edits")
    else:
        record_decision(job.id, "rejected", "skipped by user")

    print(f"-> {job.id}: done")


def main() -> None:
    with get_session() as session:
        scored_jobs = session.query(Job).filter(Job.status == "scored").all()

    if not scored_jobs:
        print("No jobs with status='scored' to review.")
        return

    for job in scored_jobs:
        review_job(job)


if __name__ == "__main__":
    main()
