from scorer.rules import score_job


def test_scores_zero_when_no_keywords_match():
    result = score_job("Sales Manager", "Manage a team of retail staff.")

    assert result.tech_match_score == 0
    assert result.status == "scored"
    assert not result.requires_citizenship
    assert not result.requires_clearance


def test_scores_matched_must_have_keywords():
    result = score_job(
        "Senior Python Engineer",
        "Build RAG pipelines with FastAPI and Python. Experience with Kafka a plus.",
    )

    assert "python" in result.matched_must_have
    assert "fastapi" in result.matched_must_have
    assert "rag" in result.matched_must_have
    assert "kafka" in result.matched_must_have
    assert result.tech_match_score > 0
    assert result.status == "scored"


def test_word_boundary_avoids_false_positive_substring_match():
    # "go" must not match inside "good" or "algorithm"
    result = score_job("Support Officer", "You have a good attitude and algorithm knowledge.")

    assert "go" not in result.matched_nice_to_have


def test_citizenship_requirement_forces_skip():
    result = score_job(
        "Backend Engineer",
        "Applicants must be an Australian citizen due to government contract requirements.",
    )

    assert result.requires_citizenship
    assert result.status == "skip"


def test_clearance_requirement_forces_skip():
    result = score_job(
        "Backend Engineer",
        "Candidate must hold or be able to obtain NV1 security clearance.",
    )

    assert result.requires_clearance
    assert result.status == "skip"


def test_not_claimed_keywords_are_tracked_but_dont_add_score():
    result = score_job("Frontend Engineer", "Must have Angular and Django experience.")

    assert "angular" in result.matched_not_claimed
    assert "django" in result.matched_not_claimed
    assert result.tech_match_score == 0
