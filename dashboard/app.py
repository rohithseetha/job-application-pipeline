"""FastAPI dashboard: browse jobs, review drafts, approve/reject, download PDFs.

Run with: uvicorn dashboard.app:app --reload
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from db.models import Job
from db.session import get_session
from review.actions import draft_dir_for, generate_draft, record_decision, update_cover_letter
from scorer.rules import score_job

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATUSES = ["fetched", "scored", "skip", "reviewed", "rejected"]

app = FastAPI(title="Job Application Pipeline")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _load_draft(job_id: str) -> dict | None:
    draft_path = draft_dir_for(job_id) / "draft.json"
    if not draft_path.exists():
        return None
    return json.loads(draft_path.read_text())


@app.get("/")
def list_jobs(request: Request, status: str = "scored"):
    with get_session() as session:
        counts = {s: session.query(Job).filter(Job.status == s).count() for s in STATUSES}
        query = session.query(Job)
        if status != "all":
            query = query.filter(Job.status == status)
        jobs = query.order_by(Job.tech_match_score.desc()).all()
        jobs_data = [
            {
                "id": j.id,
                "title": j.title,
                "company": j.company,
                "location": j.location,
                "status": j.status,
                "tech_match_score": j.tech_match_score,
            }
            for j in jobs
        ]

    return templates.TemplateResponse(
        request,
        "job_list.html",
        {"jobs": jobs_data, "counts": counts, "current_status": status},
    )


@app.get("/generate")
def generate_form(request: Request):
    return templates.TemplateResponse(request, "generate.html", {})


@app.post("/generate")
def create_adhoc_job(
    title: str = Form(...),
    company: str = Form(...),
    description: str = Form(...),
    location: str = Form(""),
):
    job_id = f"manual:{uuid.uuid4().hex[:12]}"
    result = score_job(title, description)
    with get_session() as session:
        session.add(
            Job(
                id=job_id,
                source="manual",
                title=title,
                company=company,
                location=location or None,
                description=description,
                source_url="",
                fetched_at=datetime.now(timezone.utc),
                requires_citizenship=result.requires_citizenship,
                requires_clearance=result.requires_clearance,
                tech_match_score=result.tech_match_score,
                status=result.status,
            )
        )
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


def _get_job_or_404(job_id: str) -> Job:
    with get_session() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"No job with id {job_id}")
        session.expunge(job)
        return job


@app.get("/jobs/{job_id}")
def job_detail(request: Request, job_id: str):
    job = _get_job_or_404(job_id)
    draft = _load_draft(job_id)
    return templates.TemplateResponse(
        request,
        "job_detail.html",
        {"job": job, "draft": draft, "job_dir_name": job_id.replace(":", "_")},
    )


@app.post("/jobs/{job_id}/generate")
def generate(job_id: str):
    job = _get_job_or_404(job_id)
    generate_draft(job)
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


@app.post("/jobs/{job_id}/decision")
def decision(job_id: str, status: str = Form(...), notes: str = Form("")):
    _get_job_or_404(job_id)  # 404s cleanly if the job doesn't exist
    record_decision(job_id, status, notes)
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


@app.post("/jobs/{job_id}/cover-letter")
def edit_cover_letter(job_id: str, cover_letter: str = Form(...)):
    job = _get_job_or_404(job_id)
    update_cover_letter(job, cover_letter)
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


@app.get("/jobs/{job_id}/resume.pdf")
def download_resume_pdf(job_id: str):
    path = draft_dir_for(job_id) / "resume.pdf"
    if not path.exists():
        raise HTTPException(status_code=404, detail="No resume PDF generated for this job yet")
    return FileResponse(path, media_type="application/pdf", filename="resume.pdf")


@app.get("/jobs/{job_id}/cover-letter.pdf")
def download_cover_letter_pdf(job_id: str):
    path = draft_dir_for(job_id) / "cover_letter.pdf"
    if not path.exists():
        raise HTTPException(status_code=404, detail="No cover letter PDF generated for this job yet")
    return FileResponse(path, media_type="application/pdf", filename="cover_letter.pdf")
