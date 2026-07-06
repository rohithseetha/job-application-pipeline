import shutil

import pytest

from pdfgen.render import (
    LatexCompileError,
    _paragraphs_to_latex,
    compile_latex,
    escape_latex,
    render_cover_letter_pdf,
)

pdflatex_available = shutil.which("pdflatex") or __import__("pathlib").Path(
    "/Library/TeX/texbin/pdflatex"
).exists()
requires_pdflatex = pytest.mark.skipif(
    not pdflatex_available, reason="pdflatex not installed"
)


def test_escape_latex_handles_special_characters():
    assert escape_latex("C# & 50% off $5") == r"C\# \& 50\% off \$5"


def test_escape_latex_handles_literal_backslash():
    assert escape_latex(r"a\b") == r"a\textbackslash{}b"


def test_escape_latex_handles_underscores_and_braces():
    assert escape_latex("item_name {x}") == r"item\_name \{x\}"


def test_paragraphs_to_latex_splits_on_blank_lines():
    text = "First paragraph.\n\nSecond paragraph\nstill second."
    result = _paragraphs_to_latex(text)
    assert result == "First paragraph.\n\nSecond paragraph still second."


@requires_pdflatex
def test_compile_latex_produces_pdf_bytes():
    tex = r"""\documentclass{article}
\begin{document}
Hello world.
\end{document}
"""
    pdf_bytes = compile_latex(tex, job_name="test_doc")
    assert pdf_bytes.startswith(b"%PDF")


@requires_pdflatex
def test_compile_latex_raises_on_invalid_latex():
    with pytest.raises(LatexCompileError):
        compile_latex(r"\documentclass{article}\begin{document}\badcommand{x}\end{document}")


@requires_pdflatex
def test_render_cover_letter_pdf_escapes_and_compiles():
    pdf_bytes = render_cover_letter_pdf(
        "I built APIs with 100% uptime & $0 downtime cost.",
        job_title="Senior Engineer",
        company="Acme & Co",
    )
    assert pdf_bytes.startswith(b"%PDF")
