"""API endpoint tests: demo, analyze, github import, settings status.

External LLM calls are mocked; retrieval runs for real on small inputs.
"""
import json

from app.llm import LLMError


def _finding(severity="High"):
    return {
        "severity": severity,
        "file_line": "src/auth.ts:42",
        "risk": "SQL injection via string concatenation",
        "rule_violation": "Rule 2: parameterized queries required",
        "safer_code": "cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
        "source_chunk": "Database queries must use parameterized statements.",
    }


DIFF = """diff --git a/src/api/users.py b/src/api/users.py
--- a/src/api/users.py
+++ b/src/api/users.py
@@ -1,3 +1,3 @@
-def get_user(user_id):
-    query = "SELECT * FROM users WHERE id = %s" % user_id
+def get_user(user_id):
+    query = f"SELECT * FROM users WHERE id = {user_id}"
"""
RULES = """## Rule: Parameterized Queries
Database queries must use parameterized statements. Never build SQL with
string concatenation or f-strings containing user input.
"""


def test_demo_diff(client, auth_headers):
    resp = client.get("/api/demo/diff", headers=auth_headers)
    assert resp.status_code == 200
    assert "diff" in resp.json()


def test_demo_rules(client, auth_headers):
    resp = client.get("/api/demo/rules", headers=auth_headers)
    assert resp.status_code == 200
    assert "rules" in resp.json()


def test_analyze_empty_diff_returns_friendly_error(client, auth_headers):
    resp = client.post(
        "/api/analyze", headers=auth_headers, json={"diff": "", "rules": RULES}
    )
    assert resp.status_code == 422


def test_analyze_whitespace_diff_returns_friendly_error(client, auth_headers):
    resp = client.post(
        "/api/analyze", headers=auth_headers, json={"diff": "   ", "rules": RULES}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["findings"] == []
    assert "No diff provided" in body["error"]


def test_analyze_whitespace_rules_returns_friendly_error(client, auth_headers):
    resp = client.post(
        "/api/analyze", headers=auth_headers, json={"diff": DIFF, "rules": "  "}
    )
    assert resp.status_code == 200
    assert "No rules provided" in resp.json()["error"]


def test_analyze_oversized_diff_rejected(client, auth_headers):
    resp = client.post(
        "/api/analyze",
        headers=auth_headers,
        json={"diff": "+" + "x" * (500 * 1024), "rules": RULES},
    )
    assert resp.status_code == 422


def test_analyze_success_with_mocked_llm(client, auth_headers, monkeypatch):
    from app.models import Finding

    def fake_call_llm(diff, rules_chunks):
        assert rules_chunks, "retrieval should provide rule chunks"
        return [Finding(**_finding())]

    monkeypatch.setattr("main.call_llm", fake_call_llm)
    resp = client.post(
        "/api/analyze", headers=auth_headers, json={"diff": DIFF, "rules": RULES}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    assert len(body["findings"]) == 1
    assert body["findings"][0]["severity"] == "High"
    assert len(body["screening_suggestions"]) == 1


def test_analyze_maps_llm_error_to_client_error(client, auth_headers, monkeypatch):
    def fake_call_llm(diff, rules_chunks):
        raise LLMError("The LLM provider timed out. Please try again.")

    monkeypatch.setattr("main.call_llm", fake_call_llm)
    resp = client.post(
        "/api/analyze", headers=auth_headers, json={"diff": DIFF, "rules": RULES}
    )
    assert resp.status_code == 200
    assert "timed out" in resp.json()["error"]


def test_analyze_internal_error_is_not_leaked(client, auth_headers, monkeypatch):
    def fake_call_llm(diff, rules_chunks):
        raise RuntimeError("secret internals /tmp/xyz/key.pem")

    monkeypatch.setattr("main.call_llm", fake_call_llm)
    resp = client.post(
        "/api/analyze", headers=auth_headers, json={"diff": DIFF, "rules": RULES}
    )
    assert resp.status_code == 200
    error = resp.json()["error"]
    assert "internal error" in error.lower()
    assert "key.pem" not in error


def test_settings_status_has_no_api_key(client, auth_headers):
    resp = client.get("/api/settings/status", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["llm_configured"] is True
    assert "test-api-key" not in json.dumps(body)


def test_settings_status_requires_auth(client):
    resp = client.get("/api/settings/status")
    assert resp.status_code == 401


def test_github_import_success(client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        "main.import_repository_review",
        lambda repo, pull, token: ("owner/repo", "+diff", "policy", "SECURITY.md"),
    )
    resp = client.post(
        "/api/github/import", headers=auth_headers, json={"repository": "owner/repo", "pull_number": 1}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["diff"] == "+diff"
    assert body["policy_path"] == "SECURITY.md"


def test_github_import_maps_value_error(client, auth_headers, monkeypatch):
    def fail(repo, pull, token):
        raise ValueError("Repository or pull request not found.")

    monkeypatch.setattr("main.import_repository_review", fail)
    resp = client.post(
        "/api/github/import", headers=auth_headers, json={"repository": "owner/repo"}
    )
    assert resp.status_code == 200
    assert "not found" in resp.json()["error"]


def test_github_import_internal_error_not_leaked(client, auth_headers, monkeypatch):
    def fail(repo, pull, token):
        raise RuntimeError("unexpected crash detail")

    monkeypatch.setattr("main.import_repository_review", fail)
    resp = client.post(
        "/api/github/import", headers=auth_headers, json={"repository": "owner/repo"}
    )
    assert resp.status_code == 200
    assert "unexpected crash detail" not in resp.json()["error"]


def test_unauthorized_api_requests_rejected(client):
    for method, path in (("get", "/api/demo/diff"), ("get", "/api/settings/status")):
        assert getattr(client, method)(path).status_code == 401
    assert client.post("/api/analyze", json={"diff": "d", "rules": "r"}).status_code == 401
    assert client.post("/api/github/import", json={"repository": "o/r"}).status_code == 401
