---
name: tailor-application
description: Tailor a resume diff and cover letter for a specific job posting using Rohith's master resume and honesty constraints. Use when drafting or reviewing a job application, resume edit, or cover letter for this pipeline.
---

# Tailor application

## Overview
This skill encodes the rules for generating a tailored resume diff and cover
letter from a job description. It should be used any time `draft_tailored_resume`
is invoked, or when reviewing/editing a draft manually in this repo.

## Inputs
- `master_resume.tex` — the LaTeX master resume, single source of truth for content.
- `honesty_flags.md` — constraints below, kept here for quick reference; if the
  two ever disagree, `honesty_flags.md` wins.
- The job description, title, and company for the target posting.

## Honesty constraints — never violate these
- Kotlin: framed as working experience, not a primary language.
- Go: scoped specifically to Hyperledger Fabric chaincode — do not generalize to
  "Go backend experience."
- RAG: claimed fully — this was genuinely built end-to-end, safe to state directly.
- LangChain / LangGraph / Flowise / Semantic Kernel: exploratory but actively
  deepening — safe to say "actively deepening" or "ramping up on," never
  "production experience."
- AWS Bedrock: framed as a fast ramp from Azure AI Foundry experience, not
  independent Bedrock production work.
- Anthropic Claude API: safe to claim directly — daily Claude Code user, and
  has built real tooling against the API (agent orchestration work at
  Ericsson, plus this job-application pipeline itself). Don't overstate scope
  beyond what's actually been built.
- GitHub Copilot: safe to mention as a tool used alongside Claude Code.
- Never claim: C#/.NET, Django, Angular, Redux, React Native, Cypress, or
  iPaaS/BI platforms not actually used.
- Skip roles outright (do not draft) if they require Australian citizenship or
  AGSVA/NV1 clearance — Rohith holds PR (Subclass 190), not citizenship or clearance.

## Cover letter style
- ~200 words.
- Conversational tone, contractions allowed, no em-dashes.
- Include at least one specific technical example relevant to the JD, not generic
  claims.
- Include one honest gap paragraph if the JD asks for something Rohith hasn't done —
  frame it as fast-ramp capability where there's a genuine adjacent skill, otherwise
  state the gap plainly.

## Resume diff rules
- Never rewrite the whole resume — only propose section-level edits (bullet
  reordering, emphasis shifts, added/removed lines) against the master.
- Preserve the master's accent color and LaTeX styling conventions.
- Any bullet that would violate an honesty constraint above must be flagged in
  `gap_notes`, not silently adjusted to sound closer to the JD.

## Output format
Return JSON with three keys: `resume_diff` (list of section-level edits),
`cover_letter` (~200 words per the style rules above), `gap_notes` (any honest
gaps between the JD and Rohith's real experience, plus a note if the role should
be skipped for citizenship/clearance reasons).

## Examples
**Input:** JD for a "Senior AI Engineer" role mentioning LangChain and AWS Bedrock
production experience.
**Output should:** list LangChain/Bedrock as exploratory/fast-ramp in `gap_notes`,
not claim production experience in the cover letter or resume diff, and instead
lead with the genuinely-built end-to-end RAG pipeline as the closest real match.

**Input:** JD requiring "Australian citizenship or ability to obtain NV1 clearance."
**Output should:** return `gap_notes` stating the role should be skipped, and skip
generating a resume diff or cover letter.
