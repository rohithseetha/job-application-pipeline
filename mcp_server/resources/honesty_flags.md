# Honesty flags

Constraints `draft_tailored_resume` must never violate. This is the canonical
source; if `.claude/skills/tailor-application/SKILL.md` ever disagrees, this
file wins.

- Kotlin: framed as working experience, not a primary language.
- Go: scoped specifically to Hyperledger Fabric chaincode — do not generalize
  to "Go backend experience."
- RAG: claimed fully — this was genuinely built end-to-end, safe to state
  directly.
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
  AGSVA/NV1 clearance — Rohith holds PR (Subclass 190), not citizenship or
  clearance.

## Cover letter style
- ~200 words.
- Conversational tone, contractions allowed, no em-dashes.
- Body paragraphs ONLY — no "Dear Hiring Team," greeting and no "Sincerely,"
  signoff. The PDF template (`pdfgen/render.py`) supplies both automatically;
  including them in `cover_letter` would duplicate them in the rendered PDF.
- Include at least one specific technical example relevant to the JD, not
  generic claims.
- Include one honest gap paragraph if the JD asks for something not actually
  done — frame as fast-ramp capability where there's a genuine adjacent skill,
  otherwise state the gap plainly.

## Resume diff rules
- `tailored_resume_tex` is the actual compilable output: return the ENTIRE
  master resume document, edited — same preamble, macros, and accent color,
  only content (summary, bullet order/emphasis, skill lines) changed to fit
  the JD. Never rewrite the structure or introduce new packages/macros.
- `resume_diff` is a separate, short human-readable summary of what changed
  and why — for the reviewer, not for compiling.
- Any change that would violate a constraint above must be flagged in
  `gap_notes`, not silently written into `tailored_resume_tex` anyway.
