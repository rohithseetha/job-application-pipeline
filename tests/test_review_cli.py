import json
from contextlib import contextmanager

from db.models import Job
from review import cli

APPROVED_DRAFT = {
    "resume_diff": [{"section": "Summary", "change": "Lead with RAG work", "reason": "JD asks for LLM experience"}],
    "cover_letter": "Original cover letter.",
    "gap_notes": [],
    "skip_recommended": False,
}

SKIP_DRAFT = {
    "resume_diff": [],
    "cover_letter": "",
    "gap_notes": ["Role requires NV1 clearance Rohith does not hold."],
    "skip_recommended": True,
}


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
    )
    defaults.update(overrides)
    return Job(**defaults)


def test_approve_writes_draft_and_logs(tmp_path, monkeypatch, db_session):
    monkeypatch.setattr(cli, "DRAFTS_DIR", tmp_path)
    monkeypatch.setattr(cli, "draft_tailored_resume", lambda *a, **kw: json.dumps(APPROVED_DRAFT))
    monkeypatch.setattr("builtins.input", lambda _: "a")

    logged = {}
    monkeypatch.setattr(cli, "log_application", lambda job_id, status, notes: logged.update(job_id=job_id, status=status))

    job = _make_job()
    db_session.add(job)
    db_session.commit()
    monkeypatch.setattr(cli, "get_session", lambda: _session_ctx(db_session))

    cli.review_job(job)

    assert logged == {"job_id": "adzuna:1", "status": "reviewed"}
    assert (tmp_path / "adzuna_1" / "cover_letter.txt").read_text() == "Original cover letter."
    assert db_session.get(Job, "adzuna:1").status == "reviewed"


def test_skip_recommended_and_user_confirms_rejects(tmp_path, monkeypatch, db_session):
    monkeypatch.setattr(cli, "DRAFTS_DIR", tmp_path)
    monkeypatch.setattr(cli, "draft_tailored_resume", lambda *a, **kw: json.dumps(SKIP_DRAFT))
    monkeypatch.setattr("builtins.input", lambda _: "y")

    logged = {}
    monkeypatch.setattr(cli, "log_application", lambda job_id, status, notes: logged.update(status=status))

    job = _make_job(id="adzuna:2")
    db_session.add(job)
    db_session.commit()
    monkeypatch.setattr(cli, "get_session", lambda: _session_ctx(db_session))

    cli.review_job(job)

    assert logged["status"] == "rejected"
    assert db_session.get(Job, "adzuna:2").status == "rejected"


def test_skip_recommended_and_user_declines_leaves_scored(tmp_path, monkeypatch, db_session):
    monkeypatch.setattr(cli, "DRAFTS_DIR", tmp_path)
    monkeypatch.setattr(cli, "draft_tailored_resume", lambda *a, **kw: json.dumps(SKIP_DRAFT))
    monkeypatch.setattr("builtins.input", lambda _: "n")

    job = _make_job(id="adzuna:3")
    db_session.add(job)
    db_session.commit()

    cli.review_job(job)

    assert db_session.get(Job, "adzuna:3").status == "scored"


@contextmanager
def _session_ctx(session):
    yield session
