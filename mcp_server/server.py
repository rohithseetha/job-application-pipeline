"""MCP tool server: drafts tailored applications and logs outcomes.

Tools:
    draft_tailored_resume(job_description, job_title, company) — calls an LLM
        with master_resume.tex + honesty_flags.md as system context, returns
        JSON with a full compilable tailored resume LaTeX document, a short
        human-readable resume_diff summary, a cover letter, and gap notes.
        Provider is selectable via LLM_PROVIDER ("gemini" or "anthropic";
        defaults to "gemini" since it has a genuine free tier) — both code
        paths are fully implemented.
    log_application(job_id, status, notes) — appends to application_tracker.csv.
"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types
from mcp.server.fastmcp import FastMCP

load_dotenv()

RESOURCES_DIR = Path(__file__).parent / "resources"
TRACKER_PATH = Path(__file__).resolve().parents[1] / "application_tracker.csv"
TRACKER_FIELDS = ["timestamp", "job_id", "status", "notes"]

LLM_PROVIDER = os.getenv("LLM_PROVIDER") or "gemini"  # "gemini" or "anthropic"

# Gemini: gemini-2.5-flash is free-tier eligible (Google AI Studio API key,
# no billing account needed) and is the default. Bump via GEMINI_MODEL in .env.
# `or` (not getenv's default arg) so a blank GEMINI_MODEL= line in .env still
# falls back correctly — an empty string is "set", not absent.
GEMINI_MODEL = os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"

# Anthropic: defaults to Haiku 4.5 (cheapest tier) to keep this affordable to
# run for real. Bump to claude-opus-4-8 or claude-sonnet-5 via ANTHROPIC_MODEL
# in .env once you're funding the account for better drafting quality — those
# also support adaptive thinking + effort, which Haiku 4.5 does not.
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL") or "claude-haiku-4-5"
_SUPPORTS_ADAPTIVE_THINKING = ANTHROPIC_MODEL != "claude-haiku-4-5"

RESUME_DIFF_SCHEMA = {
    "type": "object",
    "properties": {
        "resume_diff": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section": {"type": "string"},
                    "change": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["section", "change", "reason"],
                "additionalProperties": False,
            },
            "description": "Human-readable summary of what changed and why — for review, not for compiling.",
        },
        "tailored_resume_tex": {
            "type": "string",
            "description": (
                "The COMPLETE tailored resume as a single compilable LaTeX "
                "document (\\documentclass ... \\end{document}), preserving "
                "the master's preamble, macros, and styling exactly. Empty "
                "string if skip_recommended is true."
            ),
        },
        "cover_letter": {"type": "string"},
        "gap_notes": {"type": "array", "items": {"type": "string"}},
        "skip_recommended": {
            "type": "boolean",
            "description": (
                "True if the job requires citizenship or clearance Rohith "
                "doesn't hold and the application should be skipped."
            ),
        },
    },
    "required": [
        "resume_diff",
        "tailored_resume_tex",
        "cover_letter",
        "gap_notes",
        "skip_recommended",
    ],
    "additionalProperties": False,
}

mcp = FastMCP("job-application-pipeline")


def _load_system_context() -> str:
    resume = (RESOURCES_DIR / "master_resume.tex").read_text()
    honesty_flags = (RESOURCES_DIR / "honesty_flags.md").read_text()
    return (
        "You are drafting a tailored resume and cover letter for Rohith "
        "Kumar Seetha. Never fabricate or overstate experience beyond what is "
        "in the master resume and honesty flags below. If the job requires "
        "Australian citizenship or a security clearance, set "
        "skip_recommended=true, explain why in gap_notes, and return an empty "
        "string for tailored_resume_tex and cover_letter.\n\n"
        "For tailored_resume_tex: return the ENTIRE master resume document "
        "below, edited — same \\documentclass, \\usepackage lines, \\newcommand "
        "definitions, and accent color, unchanged. Only reorder/emphasize/trim "
        "bullet points and the professional summary to fit the job description; "
        "never introduce new LaTeX packages or break compilation. Escape LaTeX "
        "special characters (&, %, $, #, _) in any new text you add. "
        "resume_diff is a separate, short human-readable summary of what "
        "changed and why, for the reviewer — it does not need to be valid "
        "LaTeX.\n\n"
        f"# Master resume (LaTeX)\n{resume}\n\n"
        f"# Honesty flags and drafting rules\n{honesty_flags}"
    )


def _build_user_prompt(job_description: str, job_title: str, company: str) -> str:
    return (
        f"Job title: {job_title}\nCompany: {company}\n\n"
        f"Job description:\n{job_description}\n\n"
        "Draft the tailored resume LaTeX, resume_diff summary, cover letter, "
        "and gap notes per the rules above."
    )


def _draft_with_gemini(system: str, user_prompt: str) -> str:
    # Uses the mature generate_content API rather than the newer Interactions
    # API — as of google-genai 2.10.0, Interactions' response_format/schema
    # handling has a client-side serialization bug (server rejects it with
    # "responseFormat must be set when responseMimeType is set." even though
    # both are set) and silently falls back to unstructured text otherwise.
    client = genai.Client()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_prompt,
        config=genai_types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_json_schema=RESUME_DIFF_SCHEMA,
            # Full resume LaTeX + diff summary + cover letter + gap notes,
            # all JSON-escaped, comfortably exceeds the old 8192 budget.
            max_output_tokens=16384,
            # Flash's thinking tokens otherwise eat into max_output_tokens
            # silently and can truncate the JSON mid-string.
            thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return response.text


def _draft_with_anthropic(system: str, user_prompt: str) -> str:
    client = anthropic.Anthropic()

    output_config: dict = {"format": {"type": "json_schema", "schema": RESUME_DIFF_SCHEMA}}
    request_kwargs: dict = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 16384,
        "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": user_prompt}],
    }
    if _SUPPORTS_ADAPTIVE_THINKING:
        request_kwargs["thinking"] = {"type": "adaptive"}
        output_config["effort"] = "high"
    request_kwargs["output_config"] = output_config

    response = client.messages.create(**request_kwargs)
    return next(block.text for block in response.content if block.type == "text")


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]  # drop opening fence (with optional language tag)
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def _generate_plain_text(prompt: str, max_output_tokens: int = 16384) -> str:
    """Single plain-text (non-JSON-schema) LLM call, dispatched by LLM_PROVIDER."""
    if LLM_PROVIDER == "anthropic":
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=max_output_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = next(block.text for block in response.content if block.type == "text")
    else:
        client = genai.Client()
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                max_output_tokens=max_output_tokens,
                thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
            ),
        )
        text = response.text
    return _strip_code_fence(text)


def fix_latex_line(broken_line: str, error_message: str) -> str:
    """Ask the LLM to fix a single broken line of LaTeX.

    Used for the self-healing retry when the model's JSON-escaped LaTeX drops
    a backslash or similar — a known LLM weak spot with backslash-heavy JSON
    string content. Fixing one line at a time (rather than asking for the
    whole document back) avoids the model re-transcribing — and risking new
    escaping mistakes in — unrelated parts of the document.
    """
    prompt = (
        "This single line of LaTeX failed to compile with pdflatex:\n\n"
        f"{broken_line}\n\n"
        f"pdflatex error:\n{error_message}\n\n"
        "Return ONLY the corrected version of this one line — same content "
        "and meaning, fix only the syntax error (e.g. a missing escape "
        "backslash before a special character like & % $ # _). No markdown "
        "code fences, no explanation, no other lines."
    )
    return _generate_plain_text(prompt, max_output_tokens=2048)


def fix_tailored_resume_tex(broken_tex: str, error_message: str) -> str:
    """Ask the LLM to fix a whole LaTeX document that failed to compile.

    Fallback for when the pdflatex error doesn't include a parseable line
    number (fix_latex_line is preferred — see review/actions.py). Returns
    corrected LaTeX source (plain text, not JSON).
    """
    prompt = (
        "The following LaTeX document failed to compile with pdflatex. Fix "
        "ONLY the error below — make no other changes — and return the "
        "complete corrected document, from \\documentclass to \\end{document}, "
        "with no markdown code fences or commentary.\n\n"
        f"pdflatex error:\n{error_message}\n\n"
        f"Broken LaTeX:\n{broken_tex}"
    )
    return _generate_plain_text(prompt)


@mcp.tool()
def draft_tailored_resume(job_description: str, job_title: str, company: str) -> str:
    """Draft a tailored resume, cover letter, and gap notes for a job posting.

    Returns a JSON string with keys: resume_diff, tailored_resume_tex,
    cover_letter, gap_notes, skip_recommended. Uses LLM_PROVIDER ("gemini" by
    default, or "anthropic").
    """
    system = _load_system_context()
    user_prompt = _build_user_prompt(job_description, job_title, company)

    if LLM_PROVIDER == "anthropic":
        return _draft_with_anthropic(system, user_prompt)
    return _draft_with_gemini(system, user_prompt)


@mcp.tool()
def log_application(job_id: str, status: str, notes: str = "") -> str:
    """Append an application outcome to application_tracker.csv."""
    is_new = not TRACKER_PATH.exists()
    with TRACKER_PATH.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TRACKER_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "job_id": job_id,
                "status": status,
                "notes": notes,
            }
        )
    return f"Logged {job_id} as {status}"


if __name__ == "__main__":
    mcp.run()
