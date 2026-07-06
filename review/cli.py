"""CLI: review drafted applications for each 'scored' job.

For every job with status='scored', drafts a resume diff + cover letter
(reusing the same function mcp_server exposes as a tool), shows it, and lets
you approve, edit, or skip. Approved/edited drafts are written to
drafts/<job_id>/ and logged to application_tracker.csv; the job's DB status
updates to 'reviewed' or 'rejected'. Nothing is ever sent automatically.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from db.models import Job
from db.session import get_session
from mcp_server.server import draft_tailored_resume, log_application

DRAFTS_DIR = Path(__file__).resolve().parents[1] / "drafts"


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


def _finalize(job: Job, status: str, notes: str, draft: dict) -> None:
    job_dir = DRAFTS_DIR / job.id.replace(":", "_")
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "draft.json").write_text(json.dumps(draft, indent=2))
    (job_dir / "cover_letter.txt").write_text(draft.get("cover_letter", ""))

    log_application(job_id=job.id, status=status, notes=notes)

    with get_session() as session:
        db_job = session.get(Job, job.id)
        db_job.status = status

    print(f"-> {job.id}: {status}")


def review_job(job: Job) -> None:
    print(f"\n{'=' * 70}\n{job.title} @ {job.company}  (score: {job.tech_match_score})\n{job.source_url}\n{'=' * 70}")
    print("Drafting resume diff + cover letter...")
    draft = json.loads(draft_tailored_resume(job.description, job.title, job.company))

    if draft.get("skip_recommended"):
        print("\nModel recommends SKIPPING this job:")
        for note in draft.get("gap_notes", []):
            print(f"  - {note}")
        if _prompt_choice("Reject this job?", "yn") == "y":
            _finalize(job, status="rejected", notes="skip_recommended by model", draft=draft)
        else:
            print(f"-> {job.id}: left as 'scored' (no draft generated) for manual follow-up")
        return

    print("\n--- Resume diff ---")
    for edit in draft["resume_diff"]:
        print(f"[{edit['section']}] {edit['change']}\n    why: {edit['reason']}")
    print("\n--- Cover letter ---")
    print(draft["cover_letter"])
    if draft["gap_notes"]:
        print("\n--- Gap notes ---")
        for note in draft["gap_notes"]:
            print(f"  - {note}")

    choice = _prompt_choice("\nApprove (a) / Edit (e) / Skip (s)?", "aes")
    if choice == "a":
        _finalize(job, status="reviewed", notes="approved as drafted", draft=draft)
    elif choice == "e":
        draft["cover_letter"] = _edit_text(draft["cover_letter"])
        _finalize(job, status="reviewed", notes="approved with edits", draft=draft)
    else:
        _finalize(job, status="rejected", notes="skipped by user", draft=draft)


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
