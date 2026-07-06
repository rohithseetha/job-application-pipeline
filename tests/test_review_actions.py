import json
from contextlib import contextmanager

from db.models import Job
from review import actions

DRAFT = {
    "resume_diff": [{"section": "Summary", "change": "x", "reason": "y"}],
    "tailored_resume_tex": "\\documentclass{article}\\begin{document}x\\end{document}",
    "cover_letter": "Cover letter body.",
    "gap_notes": [],
    "skip_recommended": False,
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


def test_generate_draft_writes_artifacts_and_compiles_pdfs(monkeypatch, tmp_path):
    monkeypatch.setattr(actions, "DRAFTS_DIR", tmp_path)
    monkeypatch.setattr(actions, "draft_tailored_resume", lambda *a, **kw: json.dumps(DRAFT))
    monkeypatch.setattr(actions, "render_resume_pdf", lambda tex: b"%PDF-resume")
    monkeypatch.setattr(actions, "render_cover_letter_pdf", lambda text, title, company: b"%PDF-cover")

    job = _make_job()
    draft = actions.generate_draft(job)

    job_dir = tmp_path / "adzuna_1"
    assert draft["pdf_error"] is None
    assert (job_dir / "draft.json").exists()
    assert (job_dir / "cover_letter.txt").read_text() == "Cover letter body."
    assert (job_dir / "tailored_resume.tex").read_text() == DRAFT["tailored_resume_tex"]
    assert (job_dir / "resume.pdf").read_bytes() == b"%PDF-resume"
    assert (job_dir / "cover_letter.pdf").read_bytes() == b"%PDF-cover"


def test_generate_draft_self_heals_via_fix_retry(monkeypatch, tmp_path):
    from pdfgen.render import LatexCompileError

    monkeypatch.setattr(actions, "DRAFTS_DIR", tmp_path)
    monkeypatch.setattr(actions, "draft_tailored_resume", lambda *a, **kw: json.dumps(DRAFT))
    monkeypatch.setattr(actions, "render_cover_letter_pdf", lambda text, title, company: b"%PDF-cover")
    monkeypatch.setattr(actions, "fix_tailored_resume_tex", lambda tex, err: "FIXED_TEX")

    calls = []

    def _render_resume(tex):
        calls.append(tex)
        if tex == "FIXED_TEX":
            return b"%PDF-fixed"
        raise LatexCompileError("bad latex")

    monkeypatch.setattr(actions, "render_resume_pdf", _render_resume)

    draft = actions.generate_draft(_make_job())

    assert draft["pdf_error"] is None
    assert draft["tailored_resume_tex"] == "FIXED_TEX"
    job_dir = tmp_path / "adzuna_1"
    assert (job_dir / "tailored_resume.tex").read_text() == "FIXED_TEX"
    assert (job_dir / "resume.pdf").read_bytes() == b"%PDF-fixed"


def test_generate_draft_records_pdf_error_when_fix_retry_also_fails(monkeypatch, tmp_path):
    from pdfgen.render import LatexCompileError

    monkeypatch.setattr(actions, "DRAFTS_DIR", tmp_path)
    monkeypatch.setattr(actions, "draft_tailored_resume", lambda *a, **kw: json.dumps(DRAFT))
    monkeypatch.setattr(actions, "render_cover_letter_pdf", lambda text, title, company: b"%PDF-cover")
    monkeypatch.setattr(actions, "fix_tailored_resume_tex", lambda tex, err: "STILL_BROKEN")

    def _boom(*a, **kw):
        raise LatexCompileError("bad latex")

    monkeypatch.setattr(actions, "render_resume_pdf", _boom)

    draft = actions.generate_draft(_make_job())

    assert "resume: bad latex" in draft["pdf_error"]
    job_dir = tmp_path / "adzuna_1"
    assert (job_dir / "tailored_resume.tex").exists()
    assert not (job_dir / "resume.pdf").exists()


def test_generate_draft_skips_pdf_compilation_when_skip_recommended(monkeypatch, tmp_path):
    skip_draft = {**DRAFT, "skip_recommended": True, "tailored_resume_tex": "", "cover_letter": ""}
    monkeypatch.setattr(actions, "DRAFTS_DIR", tmp_path)
    monkeypatch.setattr(actions, "draft_tailored_resume", lambda *a, **kw: json.dumps(skip_draft))

    draft = actions.generate_draft(_make_job(id="adzuna:2"))

    assert draft["pdf_error"] is None
    job_dir = tmp_path / "adzuna_2"
    assert not (job_dir / "resume.pdf").exists()


def test_update_cover_letter_overwrites_text_and_pdf(monkeypatch, tmp_path):
    monkeypatch.setattr(actions, "DRAFTS_DIR", tmp_path)
    monkeypatch.setattr(actions, "render_cover_letter_pdf", lambda text, title, company: f"PDF:{text}".encode())

    actions.update_cover_letter(_make_job(), "New text.")

    job_dir = tmp_path / "adzuna_1"
    assert (job_dir / "cover_letter.txt").read_text() == "New text."
    assert (job_dir / "cover_letter.pdf").read_bytes() == b"PDF:New text."


def test_extract_error_line_number_takes_last_match():
    error = "some log noise l.12 earlier context\nmore noise l.57 the actual fatal error"
    assert actions._extract_error_line_number(error) == 57


def test_extract_error_line_number_returns_none_when_absent():
    assert actions._extract_error_line_number("no line info here") is None


def test_compile_resume_with_retries_fixes_single_line(monkeypatch, tmp_path):
    from pdfgen.render import LatexCompileError

    tex = "\\documentclass{article}\n\\begin{document}\nAgentic AI & LLMs\n\\end{document}"
    calls = []

    def _render(t):
        calls.append(t)
        if "Agentic AI & LLMs" in t:
            raise LatexCompileError("Misplaced alignment tab character &.\nl.3 Agentic AI & LLMs")
        return b"%PDF-ok"

    monkeypatch.setattr(actions, "render_resume_pdf", _render)
    monkeypatch.setattr(actions, "fix_latex_line", lambda line, err: "Agentic AI \\& LLMs")

    pdf_bytes, final_tex, error = actions._compile_resume_with_retries(tex, tmp_path)

    assert pdf_bytes == b"%PDF-ok"
    assert error is None
    assert "Agentic AI \\& LLMs" in final_tex
    assert len(calls) == 2  # one failure, one success after the line fix


def test_compile_resume_with_retries_falls_back_to_whole_doc_fix_without_line_number(monkeypatch, tmp_path):
    from pdfgen.render import LatexCompileError

    def _render(t):
        if t == "FIXED_WHOLE_DOC":
            return b"%PDF-ok"
        raise LatexCompileError("some error with no line marker at all")

    monkeypatch.setattr(actions, "render_resume_pdf", _render)
    monkeypatch.setattr(actions, "fix_tailored_resume_tex", lambda tex, err: "FIXED_WHOLE_DOC")

    pdf_bytes, final_tex, error = actions._compile_resume_with_retries("broken", tmp_path)

    assert pdf_bytes == b"%PDF-ok"
    assert final_tex == "FIXED_WHOLE_DOC"


def test_record_decision_logs_and_updates_status(monkeypatch, db_session):
    job = _make_job()
    db_session.add(job)
    db_session.commit()

    logged = {}
    monkeypatch.setattr(actions, "log_application", lambda job_id, status, notes: logged.update(job_id=job_id, status=status, notes=notes))
    monkeypatch.setattr(actions, "get_session", lambda: _session_ctx(db_session))

    actions.record_decision(job.id, "reviewed", "approved as drafted")

    assert logged == {"job_id": "adzuna:1", "status": "reviewed", "notes": "approved as drafted"}
    assert db_session.get(Job, "adzuna:1").status == "reviewed"


@contextmanager
def _session_ctx(session):
    yield session
