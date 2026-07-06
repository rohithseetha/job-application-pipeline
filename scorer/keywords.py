"""Keyword weights for tech_match_score, and phrases that trigger a hard skip.

TECH_KEYWORDS is provided by the user — reflects real skill depth, not just
resume claims. Keep it in sync with mcp_server/resources/honesty_flags.md.

CITIZENSHIP_PHRASES / CLEARANCE_PHRASES are a starting list, not exhaustive —
review and extend as you see postings with disqualifying language the scorer
missed.
"""

TECH_KEYWORDS = {
    # Core stack — direct, deep experience. Weight 2.
    "must_have": {
        "java": 2, "spring boot": 2, "python": 2, "fastapi": 2,
        "node.js": 2, "typescript": 2, "react": 2,
        "kafka": 2, "jms": 2,
        "oracle": 2, "pl/sql": 2,
        "azure ai foundry": 2, "rag": 2, "retrieval augmented generation": 2,
        "llm": 2, "agent": 2, "agentic": 2,
        "mcp": 2, "model context protocol": 2, "openapi": 2,
        "claude": 2, "claude code": 2,
    },

    # Adjacent / fast-ramp / exploratory — genuine but scoped. Weight 1.
    "nice_to_have": {
        "kotlin": 1,                     # working experience, not primary
        "go": 1, "golang": 1,            # scoped to Hyperledger Fabric chaincode
        "hyperledger fabric": 1, "corda": 1, "blockchain": 1, "r3 corda": 1,
        "langchain": 1, "langgraph": 1, "flowise": 1, "semantic kernel": 1,
        "aws bedrock": 1,                # fast-ramp from Azure AI Foundry
        "oauth2": 1, "oidc": 1, "jwt": 1, "azure ad": 1,
        "docker": 1, "kubernetes": 1, "microservices": 1,
        "nginx": 1, "cloudflare": 1,
        "distributed systems": 1,
    },

    # Never claimed — presence in a JD doesn't add score, but flag for gap_notes
    # rather than silently ignoring.
    "not_claimed": {
        "c#", ".net", "django", "angular", "redux",
        "react native", "cypress",
    },
}

# Rohith holds Australian PR (Subclass 190) — not citizenship, not clearance.
CITIZENSHIP_PHRASES = [
    "australian citizen",
    "must be a citizen",
    "citizenship is required",
    "australian citizenship is required",
    "au citizen only",
    "eligibility to obtain and maintain",
]

CLEARANCE_PHRASES = [
    "security clearance",
    "baseline clearance",
    "nv1",
    "nv2",
    "negative vetting",
    "agsva",
    "top secret clearance",
    "sc clearance",
]
