"""Shared draft-generation and decision-logging logic for the CLI and dashboard.

Generating a draft (LLM call + PDF compilation + writing artifacts to disk)
is decoupled from recording a human decision (tracker log + DB status) so a
dashboard can show the generated PDFs before the user approves/rejects.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from db.models import Job
from db.session import get_session
from mcp_server.server import (
    draft_tailored_resume,
    fix_latex_line,
    fix_tailored_resume_tex,
    log_application,
)
from pdfgen.render import LatexCompileError, render_cover_letter_pdf, render_resume_pdf

DRAFTS_DIR = Path(__file__).resolve().parents[1] / "drafts"

# LLMs occasionally drop a backslash when JSON-escaping heavy LaTeX content,
# and a single document can have more than one such slip — pdflatex stops at
# the first fatal error, so fixing one can just expose the next. A bounded
# retry loop handles a few compounding typos without looping forever.
_MAX_LATEX_FIX_ATTEMPTS = 3


def draft_dir_for(job_id: str) -> Path:
    return DRAFTS_DIR / job_id.replace(":", "_")


def _extract_error_line_number(error_message: str) -> int | None:
    """pdflatex reports the failing line as 'l.NN ...' — take the last match
    (closest to the fatal error) as our own source's authoritative line
    index, rather than trying to parse the log's re-wrapped display text."""
    matches = re.findall(r"\bl\.(\d+)\b", error_message)
    return int(matches[-1]) if matches else None


def _compile_resume_with_retries(tex: str, job_dir: Path) -> tuple[bytes | None, str, str | None]:
    """Try to compile tex to PDF, self-healing on failure.

    Prefers a surgical single-line fix (using the line number pdflatex
    reports) over asking the model to regenerate the whole document — that
    avoids the model re-transcribing, and risking new escaping mistakes in,
    unrelated parts of a long document. Falls back to a whole-document fix
    only if no line number is parseable from the error.

    Returns (pdf_bytes_or_None, final_tex, error_or_None).
    """
    last_error: str | None = None
    for attempt in range(_MAX_LATEX_FIX_ATTEMPTS):
        try:
            return render_resume_pdf(tex), tex, None
        except LatexCompileError as e:
            last_error = str(e)
            if attempt >= _MAX_LATEX_FIX_ATTEMPTS - 1:
                break

            line_no = _extract_error_line_number(last_error)
            lines = tex.split("\n")
            if line_no and 1 <= line_no <= len(lines):
                broken_line = lines[line_no - 1]
                fixed = fix_latex_line(broken_line, last_error).strip()
                fixed_nonblank = [ln for ln in fixed.splitlines() if ln.strip()]
                lines[line_no - 1] = fixed_nonblank[0] if fixed_nonblank else broken_line
                tex = "\n".join(lines)
            else:
                tex = fix_tailored_resume_tex(tex, last_error)

            (job_dir / "tailored_resume.tex").write_text(tex)
    return None, tex, last_error


def generate_draft(job: Job) -> dict:
    """Call the LLM, compile PDFs, and persist all artifacts for a job.

    Returns the parsed draft dict with an added 'pdf_error' key (None if both
    PDFs compiled cleanly, otherwise a message — the .tex/.txt sources are
    still written either way so nothing is lost).
    """
    draft = json.loads(draft_tailored_resume(job.description, job.title, job.company))

    job_dir = draft_dir_for(job.id)
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "draft.json").write_text(json.dumps(draft, indent=2))
    (job_dir / "cover_letter.txt").write_text(draft.get("cover_letter", ""))

    draft["pdf_error"] = None
    if not draft.get("skip_recommended") and draft.get("tailored_resume_tex"):
        (job_dir / "tailored_resume.tex").write_text(draft["tailored_resume_tex"])
        errors = []

        pdf_bytes, final_tex, error = _compile_resume_with_retries(draft["tailored_resume_tex"], job_dir)
        draft["tailored_resume_tex"] = final_tex
        if pdf_bytes is not None:
            (job_dir / "resume.pdf").write_bytes(pdf_bytes)
        else:
            errors.append(f"resume: {error}")

        try:
            cover_pdf = render_cover_letter_pdf(draft["cover_letter"], job.title, job.company)
            (job_dir / "cover_letter.pdf").write_bytes(cover_pdf)
        except LatexCompileError as e:
            errors.append(f"cover letter: {e}")

        if errors:
            draft["pdf_error"] = "; ".join(errors)

    return draft


def update_cover_letter(job: Job, new_text: str) -> None:
    """Overwrite the cover letter text and recompile its PDF (used after a
    human edit). Keeps the previous PDF if recompilation fails."""
    job_dir = draft_dir_for(job.id)
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "cover_letter.txt").write_text(new_text)

    draft_json_path = job_dir / "draft.json"
    if draft_json_path.exists():
        draft = json.loads(draft_json_path.read_text())
        draft["cover_letter"] = new_text
        draft_json_path.write_text(json.dumps(draft, indent=2))

    try:
        pdf_bytes = render_cover_letter_pdf(new_text, job.title, job.company)
        (job_dir / "cover_letter.pdf").write_bytes(pdf_bytes)
    except LatexCompileError:
        pass


def record_decision(job_id: str, status: str, notes: str) -> None:
    """Log the human decision to the tracker and update the job's DB status."""
    log_application(job_id=job_id, status=status, notes=notes)
    with get_session() as session:
        db_job = session.get(Job, job_id)
        db_job.status = status
