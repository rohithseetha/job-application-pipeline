from mcp_server import server


def test_draft_tailored_resume_defaults_to_gemini(monkeypatch):
    monkeypatch.setattr(server, "LLM_PROVIDER", "gemini")
    calls = {}
    monkeypatch.setattr(server, "_draft_with_gemini", lambda system, prompt: calls.setdefault("provider", "gemini") or "{}")
    monkeypatch.setattr(server, "_draft_with_anthropic", lambda system, prompt: calls.setdefault("provider", "anthropic") or "{}")

    server.draft_tailored_resume("desc", "title", "company")

    assert calls["provider"] == "gemini"


def test_draft_tailored_resume_uses_anthropic_when_selected(monkeypatch):
    monkeypatch.setattr(server, "LLM_PROVIDER", "anthropic")
    calls = {}
    monkeypatch.setattr(server, "_draft_with_gemini", lambda system, prompt: calls.setdefault("provider", "gemini") or "{}")
    monkeypatch.setattr(server, "_draft_with_anthropic", lambda system, prompt: calls.setdefault("provider", "anthropic") or "{}")

    server.draft_tailored_resume("desc", "title", "company")

    assert calls["provider"] == "anthropic"


def test_build_user_prompt_includes_job_fields():
    prompt = server._build_user_prompt("Build APIs", "Backend Engineer", "Acme")

    assert "Backend Engineer" in prompt
    assert "Acme" in prompt
    assert "Build APIs" in prompt
