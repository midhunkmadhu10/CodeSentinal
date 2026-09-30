"""LLM client tests — external calls mocked, no real API key needed."""
import json
from types import SimpleNamespace

import httpx
import openai
import pytest

import app.llm as llm
from app.llm import LLMError, _extract_json, _parse_findings, call_llm

VALID_ARRAY = json.dumps(
    [
        {
            "severity": "High",
            "file_line": "src/auth.ts:42",
            "risk": "SQL injection",
            "rule_violation": "Rule 2: parameterized queries",
            "safer_code": "db.query('... $1', [email])",
            "source_chunk": "Database queries must use parameterized statements.",
        },
        {
            "severity": "Low",
            "file_line": "src/log.ts:3",
            "risk": "password logged",
            "rule_violation": "Rule 1",
            "safer_code": "logger.debug('login attempt')",
            "source_chunk": "Never log sensitive data.",
        },
    ]
)


class FakeCompletions:
    """Stand-in for client.chat.completions with scripted behavior."""

    def __init__(self, script):
        self.script = script  # list of either ("content", str) or ("raise", exc)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        action, payload = self.script.pop(0)
        if action == "raise":
            raise payload
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=payload))]
        )


def install_fake_llm(monkeypatch, script):
    completions = FakeCompletions(script)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    monkeypatch.setattr(llm, "OpenAI", lambda **kwargs: client)
    return completions


# ── Prompt / parsing units ───────────────────────────────────────────────────

def test_extract_json_handles_fences():
    content = f"```json\n{VALID_ARRAY}\n```"
    assert _extract_json(content) == json.loads(VALID_ARRAY)


def test_extract_json_handles_surrounding_text():
    content = f"Here are the findings:\n{VALID_ARRAY}\nDone."
    assert _extract_json(content) == json.loads(VALID_ARRAY)


def test_extract_json_handles_object_with_findings_key():
    obj = {"findings": json.loads(VALID_ARRAY)}
    assert _extract_json(json.dumps(obj)) == obj


def test_extract_json_returns_none_on_garbage():
    assert _extract_json("this is not json at all") is None


def test_parse_findings_maps_fields():
    findings = _parse_findings(VALID_ARRAY)
    assert len(findings) == 2
    assert findings[0].severity.value == "High"
    assert findings[0].file_line == "src/auth.ts:42"


def test_parse_findings_accepts_object_wrapper():
    findings = _parse_findings(json.dumps({"findings": json.loads(VALID_ARRAY)}))
    assert len(findings) == 2


def test_parse_findings_normalizes_severity_case():
    item = json.dumps([{"severity": "HIGH", "file_line": "a:1", "risk": "r"}])
    findings = _parse_findings(item)
    assert findings[0].severity.value == "High"


def test_parse_findings_drops_invalid_severity():
    item = json.dumps(
        [
            {"severity": "Critical", "file_line": "a:1"},
            {"severity": "Low", "file_line": "b:2"},
        ]
    )
    findings = _parse_findings(item)
    assert len(findings) == 1
    assert findings[0].file_line == "b:2"


def test_parse_findings_caps_count():
    items = [{"severity": "Low", "file_line": f"f:{i}"} for i in range(80)]
    findings = _parse_findings(json.dumps(items))
    assert len(findings) == llm.MAX_FINDINGS


def test_parse_findings_raises_on_unparseable():
    with pytest.raises(LLMError):
        _parse_findings("no json here")


# ── call_llm behavior ────────────────────────────────────────────────────────

def test_call_llm_success_with_json_mode(monkeypatch):
    completions = install_fake_llm(monkeypatch, [("content", VALID_ARRAY)])
    findings = call_llm("diff text", ["rule chunk"])
    assert len(findings) == 2
    assert completions.calls[0]["response_format"] == {"type": "json_object"}


def test_call_llm_retries_without_json_mode(monkeypatch):
    request = httpx.Request("POST", "https://llm.example.invalid/v1")
    response = httpx.Response(400, request=request)
    bad_request = openai.BadRequestError("response_format unsupported", response=response, body=None)
    completions = install_fake_llm(
        monkeypatch, [("raise", bad_request), ("content", VALID_ARRAY)]
    )
    findings = call_llm("diff text", ["rule chunk"])
    assert len(findings) == 2
    assert "response_format" not in completions.calls[1]


def test_call_llm_handles_fenced_response(monkeypatch):
    install_fake_llm(monkeypatch, [("content", f"```json\n{VALID_ARRAY}\n```")])
    findings = call_llm("diff", ["rules"])
    assert len(findings) == 2


def test_call_llm_empty_response(monkeypatch):
    install_fake_llm(monkeypatch, [("content", "")])
    with pytest.raises(LLMError, match="empty response"):
        call_llm("diff", ["rules"])


def test_call_llm_unparseable_response(monkeypatch):
    install_fake_llm(monkeypatch, [("content", "I cannot analyze this.")])
    with pytest.raises(LLMError):
        call_llm("diff", ["rules"])


def test_call_llm_fails_closed_without_api_key(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(LLMError, match="LLM_API_KEY"):
        call_llm("diff", ["rules"])


def test_call_llm_timeout(monkeypatch):
    request = httpx.Request("POST", "https://llm.example.invalid/v1")
    install_fake_llm(monkeypatch, [("raise", openai.APITimeoutError(request))])
    with pytest.raises(LLMError, match="timed out"):
        call_llm("diff", ["rules"])


def test_call_llm_rate_limit(monkeypatch):
    request = httpx.Request("POST", "https://llm.example.invalid/v1")
    response = httpx.Response(429, request=request)
    install_fake_llm(
        monkeypatch,
        [("raise", openai.RateLimitError("rate limited", response=response, body=None))],
    )
    with pytest.raises(LLMError, match="rate limit"):
        call_llm("diff", ["rules"])


def test_call_llm_authentication_failure(monkeypatch):
    request = httpx.Request("POST", "https://llm.example.invalid/v1")
    response = httpx.Response(401, request=request)
    install_fake_llm(
        monkeypatch,
        [("raise", openai.AuthenticationError("bad key", response=response, body=None))],
    )
    with pytest.raises(LLMError, match="API key"):
        call_llm("diff", ["rules"])


def test_call_llm_connection_failure(monkeypatch):
    request = httpx.Request("POST", "https://llm.example.invalid/v1")
    install_fake_llm(
        monkeypatch,
        [("raise", openai.APIConnectionError(request=request))],
    )
    with pytest.raises(LLMError, match="reach the LLM provider"):
        call_llm("diff", ["rules"])
