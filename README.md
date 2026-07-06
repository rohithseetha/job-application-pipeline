# Job Application Pipeline

Fetch job postings, score them against your profile, draft a tailored resume
+ cover letter (as real PDFs) with an LLM, review everything yourself — via
CLI or a web dashboard — then log the outcome. No auto-submission — you
click send.

## Pipeline

```
fetcher/ -> db (jobs table) -> scorer/ -> mcp_server/ (LLM drafts) -> pdfgen/ (LaTeX -> PDF)
                                                                          |
                                              review/cli.py  <-or->  dashboard/app.py
                                                                          |
                                                              application_tracker.csv
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in ADZUNA_APP_ID / ADZUNA_APP_KEY / GEMINI_API_KEY
alembic upgrade head   # creates jobs.db with the jobs table
```

**PDF generation needs a LaTeX engine.** On macOS:

```bash
brew install --cask basictex
eval "$(/usr/libexec/path_helper)"   # or restart your terminal
sudo tlmgr update --self
sudo tlmgr install titlesec enumitem hyperref
```

Without this, everything else still works — the fetcher, scorer, drafting,
and review flow all run fine; only PDF compilation is skipped, and you still
get the `.tex`/`.txt` sources in `drafts/<job_id>/` to compile yourself.

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
  context, calls an LLM with a JSON schema output config, and returns a full
  compilable tailored resume LaTeX document, a short human-readable
  resume-diff summary (for review, not compiling), a ~200-word cover letter
  body, and gap notes.
- `log_application(job_id, status, notes)` — appends a row to
  `application_tracker.csv`.

**Provider is selectable** via `LLM_PROVIDER` in `.env` — both code paths are
fully implemented:

| `LLM_PROVIDER` | Default model | Notes |
| --- | --- | --- |
| `gemini` (default) | `gemini-2.5-flash` | Genuine free tier — get a key at https://aistudio.google.com/apikey, no billing account needed |
| `anthropic` | `claude-haiku-4-5` | Needs API credit balance at console.anthropic.com; bump to `claude-opus-4-8` via `ANTHROPIC_MODEL` for better quality |

Honesty constraints (what the model may and may not claim) live in
`mcp_server/resources/honesty_flags.md`, mirrored as a Claude Code project
skill at `.claude/skills/tailor-application/SKILL.md` for interactive use in
this repo.

**Self-healing LaTeX retry:** LLMs occasionally drop a backslash when
JSON-escaping heavy LaTeX content, which breaks compilation. `review/actions.py`
retries up to 3 times, using pdflatex's own reported line number to ask the
model to fix just that one line (not regenerate the whole document, which
risks introducing new errors elsewhere). This is not bulletproof — free/cheap
models occasionally still fail after all retries — but it resolves most
single-typo cases. On failure the `.tex`/`.txt` sources are still saved so you
can fix and compile manually.

Run the server standalone (stdio transport, for an MCP client like Claude
Desktop or Claude Code):

```bash
python -m mcp_server.server
```

Both `review/cli.py` and `dashboard/app.py` import `draft_tailored_resume`
directly and call it in-process — you don't need the server running for
either.

## Stage 4 — Review

Two ways to review — pick whichever fits:

### CLI

```bash
python -m review.cli
```

Goes through every job with `status=scored` in one interactive terminal
session: drafts a resume + cover letter (compiling both to PDF), shows a
summary, and prompts **Approve / Edit / Skip**.

### Dashboard

```bash
uvicorn dashboard.app:app --reload
```

Open http://127.0.0.1:8000. Lets you:
- Browse jobs by status (Scored / Reviewed / Rejected / Skip / Fetched)
- Generate a draft for any job, one at a time, and preview/download the
  resume and cover letter PDFs before deciding
- Edit the cover letter text inline and recompile its PDF
- Approve / Reject with one click
- **"+ Generate for a job description"** — paste any job title/company/
  description that never went through the fetcher (e.g. from LinkedIn) and
  get a tailored resume + cover letter for it, same as any fetched job

Both surfaces write to the same place: approved/edited drafts land in
`drafts/<job_id>/` (`draft.json`, `tailored_resume.tex`, `cover_letter.txt`,
`resume.pdf`, `cover_letter.pdf`), get logged to `application_tracker.csv`,
and update the job's DB status to `reviewed` or `rejected`. If the model
recommends skipping (citizenship/clearance mismatch it caught independently
of the scorer), you confirm before it's marked `rejected`.

Nothing is ever sent automatically — you take the PDFs and apply yourself.

## Tests

```bash
pytest
```

Covers the fetcher normalizer/upsert, the scorer's keyword matching and skip
logic, `pdfgen`'s LaTeX escaping and compilation (skipped automatically if no
LaTeX engine is installed), the review CLI and dashboard's approve/edit/skip
flows, and mcp_server's provider routing. All LLM calls, PDF compilation, and
the tracker are mocked in the flow tests — no API key, network, or LaTeX
install needed to run the suite (only `test_pdfgen.py`'s compilation tests
need pdflatex, and those self-skip without it).
