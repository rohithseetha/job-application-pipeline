import json
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from dashboard import app as dashboard_app
from db.models import Job

client = TestClient(dashboard_app.app)


@contextmanager
def _session_ctx(session):
    yield session


def _make_job(**overrides) -> Job:
    defaults = dict(
        id="adzuna:1",
        source="adzuna",
        title="Senior Python Engineer",
        company="Acme",
        location="Sydney",
        description="Build RAG pipelines with FastAPI.",
        source_url="https://example.com/1",
        status="scored",
        tech_match_score=42.0,
        fetched_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return Job(**defaults)


def _use_draft_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(dashboard_app, "draft_dir_for", lambda job_id: tmp_path / job_id.replace(":", "_"))


@pytest.fixture
def db(monkeypatch, db_session):
    monkeypatch.setattr(dashboard_app, "get_session", lambda: _session_ctx(db_session))
    return db_session


def test_list_jobs_default_status_is_scored(db):
    db.add(_make_job(id="adzuna:1", status="scored"))
    db.add(_make_job(id="adzuna:2", status="rejected"))
    db.commit()

    r = client.get("/")

    assert r.status_code == 200
    assert "Senior Python Engineer" in r.text


def test_list_jobs_filters_by_status(db):
    db.add(_make_job(id="adzuna:1", title="Scored Job", status="scored"))
    db.add(_make_job(id="adzuna:2", title="Rejected Job", status="rejected"))
    db.commit()

    r = client.get("/?status=rejected")

    assert "Rejected Job" in r.text
    assert "Scored Job" not in r.text


def test_job_detail_404_for_unknown_job(db):
    r = client.get("/jobs/does:not-exist")
    assert r.status_code == 404


def test_job_detail_shows_generate_button_when_no_draft(db, monkeypatch, tmp_path):
    _use_draft_dir(monkeypatch, tmp_path)
    db.add(_make_job())
    db.commit()

    r = client.get("/jobs/adzuna:1")

    assert r.status_code == 200
    assert "Generate resume" in r.text


def test_job_detail_shows_draft_when_present(db, monkeypatch, tmp_path):
    _use_draft_dir(monkeypatch, tmp_path)
    db.add(_make_job())
    db.commit()

    job_dir = tmp_path / "adzuna_1"
    job_dir.mkdir()
    draft = {
        "resume_diff": [{"section": "Summary", "change": "x", "reason": "y"}],
        "tailored_resume_tex": "",
        "cover_letter": "A cover letter.",
        "gap_notes": [],
        "skip_recommended": False,
        "pdf_error": None,
    }
    (job_dir / "draft.json").write_text(json.dumps(draft))

    r = client.get("/jobs/adzuna:1")

    assert "Resume diff" in r.text
    assert "A cover letter." in r.text


def test_generate_route_calls_generate_draft_and_redirects(db, monkeypatch, tmp_path):
    _use_draft_dir(monkeypatch, tmp_path)
    db.add(_make_job())
    db.commit()

    called = {}
    monkeypatch.setattr(dashboard_app, "generate_draft", lambda job: called.setdefault("job_id", job.id))

    r = client.post("/jobs/adzuna:1/generate", follow_redirects=False)

    assert r.status_code == 303
    assert r.headers["location"] == "/jobs/adzuna:1"
    assert called["job_id"] == "adzuna:1"


def test_decision_route_calls_record_decision_and_redirects(db, monkeypatch, tmp_path):
    _use_draft_dir(monkeypatch, tmp_path)
    db.add(_make_job())
    db.commit()

    recorded = {}
    monkeypatch.setattr(
        dashboard_app,
        "record_decision",
        lambda job_id, status, notes: recorded.update(job_id=job_id, status=status, notes=notes),
    )

    r = client.post(
        "/jobs/adzuna:1/decision",
        data={"status": "reviewed", "notes": "approved via dashboard"},
        follow_redirects=False,
    )

    assert r.status_code == 303
    assert recorded == {"job_id": "adzuna:1", "status": "reviewed", "notes": "approved via dashboard"}


def test_cover_letter_edit_route_calls_update_cover_letter(db, monkeypatch, tmp_path):
    _use_draft_dir(monkeypatch, tmp_path)
    db.add(_make_job())
    db.commit()

    updated = {}
    monkeypatch.setattr(
        dashboard_app, "update_cover_letter", lambda job, text: updated.update(job_id=job.id, text=text)
    )

    r = client.post("/jobs/adzuna:1/cover-letter", data={"cover_letter": "New text."}, follow_redirects=False)

    assert r.status_code == 303
    assert updated == {"job_id": "adzuna:1", "text": "New text."}


def test_download_resume_pdf_404_when_missing(db, monkeypatch, tmp_path):
    _use_draft_dir(monkeypatch, tmp_path)
    db.add(_make_job())
    db.commit()

    r = client.get("/jobs/adzuna:1/resume.pdf")

    assert r.status_code == 404


def test_download_resume_pdf_200_when_exists(db, monkeypatch, tmp_path):
    _use_draft_dir(monkeypatch, tmp_path)
    db.add(_make_job())
    db.commit()

    job_dir = tmp_path / "adzuna_1"
    job_dir.mkdir()
    (job_dir / "resume.pdf").write_bytes(b"%PDF-fake")

    r = client.get("/jobs/adzuna:1/resume.pdf")

    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content == b"%PDF-fake"


def test_adhoc_generate_creates_job_with_scoring_and_redirects(db):
    r = client.post(
        "/generate",
        data={
            "title": "Cleared Engineer",
            "company": "DefenceCo",
            "description": "Must hold NV1 security clearance. Python required.",
            "location": "Canberra",
        },
        follow_redirects=False,
    )

    assert r.status_code == 303
    job_id = r.headers["location"].split("/jobs/")[1]
    job = db.get(Job, job_id)
    assert job.title == "Cleared Engineer"
    assert job.requires_clearance is True
    assert job.status == "skip"
