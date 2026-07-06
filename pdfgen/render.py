"""Compile LaTeX (tailored resume + cover letter) to PDF via pdflatex."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

# BasicTeX/MacTeX installs pdflatex here but it isn't always on PATH for
# non-login shells (e.g. this process). Check PATH first, then common
# install locations.
_PDFLATEX_CANDIDATES = [
    "/Library/TeX/texbin/pdflatex",
    "/usr/local/texlive/2026basic/bin/universal-darwin/pdflatex",
    "/usr/local/bin/pdflatex",
    "/usr/bin/pdflatex",
]

APPLICANT_NAME = "Rohith Kumar Seetha"
APPLICANT_EMAIL = "rohithseetha@gmail.com"
APPLICANT_PHONE = "+61 401 415 174"
APPLICANT_LINKEDIN = "linkedin.com/in/rohith-seetha-8272b11b"
APPLICANT_GITHUB = "github.com/rohithseetha"

_LATEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


class LatexCompileError(RuntimeError):
    """Raised when pdflatex fails to produce a PDF. Message includes the log tail."""


def find_pdflatex() -> str:
    found = shutil.which("pdflatex")
    if found:
        return found
    for candidate in _PDFLATEX_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    raise LatexCompileError(
        "pdflatex not found on PATH or in common install locations. "
        "Install a LaTeX distribution (e.g. `brew install --cask basictex`)."
    )


def escape_latex(text: str) -> str:
    """Escape LaTeX special characters in plain text (not for LaTeX source)."""
    return "".join(_LATEX_ESCAPES.get(ch, ch) for ch in text)


def _paragraphs_to_latex(text: str) -> str:
    """Blank-line-separated paragraphs become LaTeX paragraphs; stray single
    newlines within a paragraph collapse to a space rather than breaking
    LaTeX's own paragraph logic unexpectedly."""
    paragraphs = [p.strip() for p in text.strip().split("\n\n") if p.strip()]
    escaped = [escape_latex(" ".join(p.split("\n"))) for p in paragraphs]
    return "\n\n".join(escaped)


def compile_latex(tex_source: str, job_name: str = "document") -> bytes:
    """Compile a complete LaTeX document to PDF bytes.

    Raises LatexCompileError (with the pdflatex log tail) if compilation
    fails or no PDF is produced.
    """
    pdflatex = find_pdflatex()

    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = Path(tmpdir) / f"{job_name}.tex"
        pdf_path = Path(tmpdir) / f"{job_name}.pdf"
        tex_path.write_text(tex_source)

        result = subprocess.run(
            [pdflatex, "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if not pdf_path.exists():
            log_tail = "\n".join(result.stdout.splitlines()[-40:])
            raise LatexCompileError(f"pdflatex failed to produce a PDF:\n{log_tail}")

        return pdf_path.read_bytes()


def render_resume_pdf(tailored_resume_tex: str) -> bytes:
    """Compile a tailored resume's full LaTeX document to PDF."""
    return compile_latex(tailored_resume_tex, job_name="resume")


def render_cover_letter_pdf(cover_letter_text: str, job_title: str, company: str) -> bytes:
    """Wrap plain cover letter text in a LaTeX template matching the resume's
    styling, and compile to PDF."""
    body = _paragraphs_to_latex(cover_letter_text)
    tex_source = _COVER_LETTER_TEMPLATE.format(
        job_title=escape_latex(job_title),
        company=escape_latex(company),
        body=body,
        name=APPLICANT_NAME,
        email=APPLICANT_EMAIL,
        phone=APPLICANT_PHONE,
        linkedin=APPLICANT_LINKEDIN,
        github=APPLICANT_GITHUB,
    )
    return compile_latex(tex_source, job_name="cover_letter")


_COVER_LETTER_TEMPLATE = r"""\documentclass[11pt,a4paper]{{article}}

\usepackage[T1]{{fontenc}}
\usepackage[utf8]{{inputenc}}
\usepackage{{lmodern}}
\usepackage[margin=1in]{{geometry}}
\usepackage{{xcolor}}
\usepackage{{hyperref}}

\definecolor{{accent}}{{RGB}}{{31,78,121}}
\hypersetup{{colorlinks=true, urlcolor=accent, linkcolor=accent}}
\pagestyle{{empty}}

\begin{{document}}

\begin{{center}}
  {{\Huge \textbf{{{name}}}}}\\[0.3em]
  \href{{mailto:{email}}}{{{email}}} \;|\; {phone} \;|\;
  \href{{https://{linkedin}}}{{{linkedin}}} \;|\;
  \href{{https://{github}}}{{{github}}}
\end{{center}}

\vspace{{1.5em}}
\today

\vspace{{1em}}
\textbf{{\color{{accent}}Re: {job_title} at {company}}}

\vspace{{1em}}
{body}

\vspace{{1.5em}}
Sincerely,\\
{name}

\end{{document}}
"""
