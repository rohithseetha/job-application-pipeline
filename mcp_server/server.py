"""MCP tool server: drafts tailored applications and logs outcomes.

Tools:
    draft_tailored_resume(job_description, job_title, company) — calls the
        Claude API with master_resume.tex + honesty_flags.md as system
        context, returns a JSON resume diff / cover letter / gap notes.
    log_application(job_id, status, notes) — appends to application_tracker.csv.
"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from mcp.server.fastmcp import FastMCP

RESOURCES_DIR = Path(__file__).parent / "resources"
TRACKER_PATH = Path(__file__).resolve().parents[1] / "application_tracker.csv"
TRACKER_FIELDS = ["timestamp", "job_id", "status", "notes"]

# Defaults to Haiku 4.5 (cheapest tier) to keep this affordable to run for
# real. Bump to claude-opus-4-8 or claude-sonnet-5 via ANTHROPIC_MODEL in
# .env once you're funding the account for better drafting quality — those
# also support adaptive thinking + effort, which Haiku 4.5 does not.
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
_SUPPORTS_ADAPTIVE_THINKING = MODEL != "claude-haiku-4-5"

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
    "required": ["resume_diff", "cover_letter", "gap_notes", "skip_recommended"],
    "additionalProperties": False,
}

mcp = FastMCP("job-application-pipeline")


def _load_system_context() -> str:
    resume = (RESOURCES_DIR / "master_resume.tex").read_text()
    honesty_flags = (RESOURCES_DIR / "honesty_flags.md").read_text()
    return (
        "You are drafting a tailored resume diff and cover letter for Rohith "
        "Kumar Seetha. Never fabricate or overstate experience beyond what is "
        "in the master resume and honesty flags below. If the job requires "
        "Australian citizenship or a security clearance, set "
        "skip_recommended=true, explain why in gap_notes, and return an empty "
        "resume_diff and cover_letter.\n\n"
        f"# Master resume (LaTeX)\n{resume}\n\n"
        f"# Honesty flags and drafting rules\n{honesty_flags}"
    )


@mcp.tool()
def draft_tailored_resume(job_description: str, job_title: str, company: str) -> str:
    """Draft a tailored resume diff, cover letter, and gap notes for a job posting.

    Returns a JSON string with keys: resume_diff, cover_letter, gap_notes,
    skip_recommended.
    """
    client = anthropic.Anthropic()
    system = _load_system_context()

    output_config: dict = {"format": {"type": "json_schema", "schema": RESUME_DIFF_SCHEMA}}
    request_kwargs: dict = {
        "model": MODEL,
        "max_tokens": 4096,
        "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Job title: {job_title}\nCompany: {company}\n\n"
                    f"Job description:\n{job_description}\n\n"
                    "Draft the tailored resume diff, cover letter, and gap "
                    "notes per the rules above."
                ),
            }
        ],
    }
    if _SUPPORTS_ADAPTIVE_THINKING:
        request_kwargs["thinking"] = {"type": "adaptive"}
        output_config["effort"] = "high"
    request_kwargs["output_config"] = output_config

    response = client.messages.create(**request_kwargs)

    return next(block.text for block in response.content if block.type == "text")


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
