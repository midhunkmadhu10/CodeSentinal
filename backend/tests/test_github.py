"""GitHub importer tests — network calls mocked."""
import io
import json
from email.message import Message
from urllib.error import HTTPError

import pytest

import app.github as github
from app.github import import_repository_review, parse_repository


def _http_error(code: int, headers: Message | None = None) -> HTTPError:
    return HTTPError("https://api.github.com/x", code, "err", headers or Message(), io.BytesIO(b"{}"))


# ── Repository parsing ───────────────────────────────────────────────────────

def test_parse_repository_plain():
    assert parse_repository("owner/repo") == ("owner", "repo")


def test_parse_repository_url():
    assert parse_repository("https://github.com/owner/repo") == ("owner", "repo")


def test_parse_repository_git_suffix_and_slash():
    assert parse_repository("https://github.com/owner/repo.git/") == ("owner", "repo")


def test_parse_repository_rejects_garbage():
    with pytest.raises(ValueError):
        parse_repository("not a repository")
    with pytest.raises(ValueError):
        parse_repository("https://gitlab.com/owner/repo")


# ── Error mapping ────────────────────────────────────────────────────────────

def test_request_json_not_found(monkeypatch):
    monkeypatch.setattr(github, "urlopen", lambda req, timeout: (_ for _ in ()).throw(_http_error(404)))
    with pytest.raises(ValueError, match="not found"):
        github._request_json("https://api.github.com/x", None)


def test_request_json_auth_failure(monkeypatch):
    monkeypatch.setattr(github, "urlopen", lambda req, timeout: (_ for _ in ()).throw(_http_error(401)))
    with pytest.raises(ValueError, match="credentials"):
        github._request_json("https://api.github.com/x", "tok")


def test_request_json_rate_limited(monkeypatch):
    headers = Message()
    headers["X-RateLimit-Remaining"] = "0"
    monkeypatch.setattr(
        github, "urlopen", lambda req, timeout: (_ for _ in ()).throw(_http_error(403, headers))
    )
    with pytest.raises(ValueError, match="rate limit"):
        github._request_json("https://api.github.com/x", None)


def test_request_json_network_error(monkeypatch):
    from urllib.error import URLError

    monkeypatch.setattr(
        github, "urlopen", lambda req, timeout: (_ for _ in ()).throw(URLError("no dns"))
    )
    with pytest.raises(ValueError, match="unreachable"):
        github._request_json("https://api.github.com/x", None)


def test_request_text_oversized_diff(monkeypatch):
    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    big = b"+" + b"x" * (github.MAX_DIFF_BYTES + 10)
    monkeypatch.setattr(github, "urlopen", lambda req, timeout: FakeResponse(big))
    with pytest.raises(ValueError, match="too large"):
        github._request_text("https://api.github.com/x", None)


# ── Import flow ──────────────────────────────────────────────────────────────

def test_import_flow_with_pull_number(monkeypatch):
    monkeypatch.setattr(github, "_request_json", lambda url, tok: {"ok": True})
    monkeypatch.setattr(github, "_request_text", lambda url, tok: "diff --git a/x b/x")
    monkeypatch.setattr(github, "_load_policy", lambda o, r, tok: ("policy", "SECURITY.md"))
    repository, diff, policy, path = import_repository_review("owner/repo", 7, None)
    assert repository == "owner/repo"
    assert diff.startswith("diff --git")
    assert policy == "policy"
    assert path == "SECURITY.md"


def test_import_flow_latest_commit(monkeypatch):
    calls = []

    def fake_json(url, tok):
        calls.append(url)
        if "/commits" in url:
            return [{"sha": "headsha", "parents": [{"sha": "basesha"}]}]
        return {"default_branch": "main"}

    def fake_text(url, tok):
        calls.append(url)
        return "+line\n"

    monkeypatch.setattr(github, "_request_json", fake_json)
    monkeypatch.setattr(github, "_request_text", fake_text)
    monkeypatch.setattr(github, "_load_policy", lambda o, r, tok: (None, None))
    repository, diff, policy, path = import_repository_review("owner/repo", None, None)
    assert any("compare/basesha...headsha" in c for c in calls)
    assert policy is None


def test_import_flow_empty_diff(monkeypatch):
    monkeypatch.setattr(github, "_request_json", lambda url, tok: {"ok": True})
    monkeypatch.setattr(github, "_request_text", lambda url, tok: "   ")
    with pytest.raises(ValueError, match="empty diff"):
        import_repository_review("owner/repo", 1, None)


def test_token_is_used_only_in_header(monkeypatch):
    captured = {}

    def fake_json(url, tok):
        captured["token"] = tok
        return {"ok": True}

    monkeypatch.setattr(github, "_request_json", fake_json)
    monkeypatch.setattr(github, "_request_text", lambda url, tok: "+x")
    monkeypatch.setattr(github, "_load_policy", lambda o, r, tok: (None, None))
    import_repository_review("owner/repo", 1, "secret-token")
    assert captured["token"] == "secret-token"
