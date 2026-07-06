# Job Application Pipeline

Fetch job postings, score them against your profile, draft a tailored resume
diff + cover letter with Claude, review everything yourself, then log the
outcome. No auto-submission — you click send.

## Pipeline

```
fetcher/  -> db (jobs table) -> scorer/ -> mcp_server/ (Claude drafts) -> review/ (CLI) -> application_tracker.csv
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in ADZUNA_APP_ID / ADZUNA_APP_KEY / ANTHROPIC_API_KEY
alembic upgrade head   # creates jobs.db with the jobs table
```

## Stage 1 — Fetch

Adzuna is the first source (official public API, requires a free key from
https://developer.adzuna.com/signup). Seek was considered first but its
`robots.txt` disallows automated access to `/api/jobsearch/` and job pages, so
it was dropped in favor of a source with clear terms for programmatic use.

```bash
python -m fetcher.adzuna --what "python developer" --where "Sydney" --pages 2
```

Inserts newly-seen postings into the `jobs` table with `status=fetched`.
Existing rows (and their scoring/review status) are left untouched on re-fetch.

## Stage 2 — Score

Rules-based: flags citizenship/clearance requirements as a hard skip
(`scorer/keywords.py` → `CITIZENSHIP_PHRASES` / `CLEARANCE_PHRASES` — review
and extend these, they're a starting list, not exhaustive), and computes
`tech_match_score` (0–100) from a weighted keyword list also in
`scorer/keywords.py` (`TECH_KEYWORDS`, must-have vs nice-to-have).

```bash
python -m scorer.run
```

Scores every job with `status=fetched`, updating `requires_citizenship`,
`requires_clearance`, `tech_match_score`, and `status` (→ `skip` or `scored`).

## Stage 3 — Draft (MCP server)

`mcp_server/server.py` exposes two tools via the official MCP Python SDK:

- `draft_tailored_resume(job_description, job_title, company)` — loads
  `mcp_server/resources/master_resume.tex` and `honesty_flags.md` as system
  context, calls Claude (`claude-opus-4-8`) with a JSON schema output config,
  and returns a resume diff + ~200-word cover letter + gap notes.
- `log_application(job_id, status, notes)` — appends a row to
  `application_tracker.csv`.

Honesty constraints (what Claude may and may not claim) live in
`mcp_server/resources/honesty_flags.md`, mirrored as a Claude Code project
skill at `.claude/skills/tailor-application/SKILL.md` for interactive use in
this repo.

Run the server standalone (stdio transport, for an MCP client like Claude
Desktop or Claude Code):

```bash
python -m mcp_server.server
```

The `review` CLI (below) also imports `draft_tailored_resume` directly and
calls it in-process — you don't need the server running just to review jobs.

## Stage 4 — Review

```bash
python -m review.cli
```

For every job with `status=scored`: drafts a resume diff + cover letter,
shows them, and prompts **Approve / Edit / Skip**. Approved (or edited)
drafts are written to `drafts/<job_id>/` (`draft.json` + `cover_letter.txt`)
for you to actually use when sending, logged to `application_tracker.csv`,
and the job's DB status updates to `reviewed` or `rejected`. If Claude
recommends skipping (citizenship/clearance mismatch it caught independently
of the scorer), you confirm before it's marked `rejected`.

Nothing is ever sent automatically — you take the reviewed draft and apply
yourself.

## Tests

```bash
pytest
```

Covers the fetcher normalizer/upsert, the scorer's keyword matching and
skip logic, and the review CLI's approve/edit/skip flow (Claude calls and
the tracker are mocked — no API key or network needed to run tests).
