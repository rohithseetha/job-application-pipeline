from db.models import Job
from review import cli

APPROVED_DRAFT = {
    "resume_diff": [{"section": "Summary", "change": "Lead with RAG work", "reason": "JD asks for LLM experience"}],
    "tailored_resume_tex": "\\documentclass{article}\\begin{document}x\\end{document}",
    "cover_letter": "Original cover letter.",
    "gap_notes": [],
    "skip_recommended": False,
    "pdf_error": None,
}

SKIP_DRAFT = {
    "resume_diff": [],
    "tailored_resume_tex": "",
    "cover_letter": "",
    "gap_notes": ["Role requires NV1 clearance Rohith does not hold."],
    "skip_recommended": True,
    "pdf_error": None,
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


def test_approve_records_decision(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "generate_draft", lambda job: dict(APPROVED_DRAFT))
    monkeypatch.setattr(cli, "draft_dir_for", lambda job_id: tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "a")

    recorded = {}
    monkeypatch.setattr(
        cli, "record_decision", lambda job_id, status, notes: recorded.update(job_id=job_id, status=status, notes=notes)
    )

    cli.review_job(_make_job())

    assert recorded == {"job_id": "adzuna:1", "status": "reviewed", "notes": "approved as drafted"}


def test_edit_updates_cover_letter_then_records_decision(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "generate_draft", lambda job: dict(APPROVED_DRAFT))
    monkeypatch.setattr(cli, "draft_dir_for", lambda job_id: tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "e")
    monkeypatch.setattr(cli, "_edit_text", lambda text: "Edited cover letter.")

    updated = {}
    monkeypatch.setattr(cli, "update_cover_letter", lambda job, text: updated.update(job_id=job.id, text=text))
    recorded = {}
    monkeypatch.setattr(
        cli, "record_decision", lambda job_id, status, notes: recorded.update(job_id=job_id, status=status, notes=notes)
    )

    cli.review_job(_make_job())

    assert updated == {"job_id": "adzuna:1", "text": "Edited cover letter."}
    assert recorded["status"] == "reviewed"
    assert recorded["notes"] == "approved with edits"


def test_skip_records_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "generate_draft", lambda job: dict(APPROVED_DRAFT))
    monkeypatch.setattr(cli, "draft_dir_for", lambda job_id: tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "s")

    recorded = {}
    monkeypatch.setattr(
        cli, "record_decision", lambda job_id, status, notes: recorded.update(job_id=job_id, status=status, notes=notes)
    )

    cli.review_job(_make_job())

    assert recorded == {"job_id": "adzuna:1", "status": "rejected", "notes": "skipped by user"}


def test_skip_recommended_and_user_confirms_rejects(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "generate_draft", lambda job: dict(SKIP_DRAFT))
    monkeypatch.setattr(cli, "draft_dir_for", lambda job_id: tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "y")

    recorded = {}
    monkeypatch.setattr(
        cli, "record_decision", lambda job_id, status, notes: recorded.update(job_id=job_id, status=status, notes=notes)
    )

    cli.review_job(_make_job(id="adzuna:2"))

    assert recorded == {"job_id": "adzuna:2", "status": "rejected", "notes": "skip_recommended by model"}


def test_skip_recommended_and_user_declines_leaves_scored(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "generate_draft", lambda job: dict(SKIP_DRAFT))
    monkeypatch.setattr(cli, "draft_dir_for", lambda job_id: tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "n")

    called = []
    monkeypatch.setattr(cli, "record_decision", lambda *a, **kw: called.append((a, kw)))

    cli.review_job(_make_job(id="adzuna:3"))

    assert called == []
