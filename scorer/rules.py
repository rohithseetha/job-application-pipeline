"""Rules-based scoring: citizenship/clearance skip flags + tech_match_score."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from scorer.keywords import CITIZENSHIP_PHRASES, CLEARANCE_PHRASES, TECH_KEYWORDS

_TOTAL_POSSIBLE_WEIGHT = sum(TECH_KEYWORDS["must_have"].values()) + sum(
    TECH_KEYWORDS["nice_to_have"].values()
)


def _phrase_pattern(phrase: str) -> re.Pattern:
    return re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE)


def _find_matches(text: str, phrases) -> list[str]:
    return [phrase for phrase in phrases if _phrase_pattern(phrase).search(text)]


@dataclass
class ScoringResult:
    requires_citizenship: bool
    requires_clearance: bool
    tech_match_score: float
    status: str
    matched_must_have: list[str] = field(default_factory=list)
    matched_nice_to_have: list[str] = field(default_factory=list)
    matched_not_claimed: list[str] = field(default_factory=list)


def score_job(title: str, description: str) -> ScoringResult:
    text = f"{title}\n{description}"

    requires_citizenship = bool(_find_matches(text, CITIZENSHIP_PHRASES))
    requires_clearance = bool(_find_matches(text, CLEARANCE_PHRASES))

    matched_must = _find_matches(text, TECH_KEYWORDS["must_have"])
    matched_nice = _find_matches(text, TECH_KEYWORDS["nice_to_have"])
    matched_not_claimed = _find_matches(text, TECH_KEYWORDS["not_claimed"])

    matched_weight = sum(TECH_KEYWORDS["must_have"][k] for k in matched_must) + sum(
        TECH_KEYWORDS["nice_to_have"][k] for k in matched_nice
    )
    tech_match_score = round(matched_weight / _TOTAL_POSSIBLE_WEIGHT * 100, 1)

    status = "skip" if (requires_citizenship or requires_clearance) else "scored"

    return ScoringResult(
        requires_citizenship=requires_citizenship,
        requires_clearance=requires_clearance,
        tech_match_score=tech_match_score,
        status=status,
        matched_must_have=matched_must,
        matched_nice_to_have=matched_nice,
        matched_not_claimed=matched_not_claimed,
    )
