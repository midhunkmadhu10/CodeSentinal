"""GitHub service layer: tree/blob fetch, PR metadata, comments, webhooks.

Builds on the low-level client in `app/github.py` (stdlib urllib, user-safe
ValueError messages). Access tokens are request-scoped and never logged or
persisted. Webhook payloads are verified with HMAC-SHA256.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from .github import parse_repository

logger = logging.getLogger("codesentinal.github")

API_ROOT = "https://api.github.com"
MAX_BLOB_BYTES = 1 * 1024 * 1024  # refuse to buffer absurd individual files
WEBHOOK_MAX_BODY = 25 * 1024 * 1024

# Re-export for the legacy import surface used by tests.
__all__ = [
    "parse_repository",
    "fetch_repo_tree",
    "fetch_blob",
    "fetch_pr_metadata",
    "fetch_pr_diff",
    "post_pr_comment",
    "verify_webhook_signature",
    "bot_token",
]


def bot_token(request_token: Optional[str] = None) -> Optional[str]:
    """Server-side bot token (GITHUB_TOKEN) unless a request supplies its own."""
    import os

    token = (request_token or os.getenv("GITHUB_TOKEN", "")).strip()
    return token or None


# ── Raw HTTP helpers (reuse github.py's error mapping where possible) ────────

def _request_json(
    url: str,
    access_token: Optional[str],
    method: str = "GET",
    body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    import json as _json
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen

    from .github import _headers  # shared header builder

    data = _json.dumps(body).encode("utf-8") if body is not None else None
    headers = _headers({"Accept": "application/vnd.github+json"}, access_token)
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=20) as response:
            return _json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            raise ValueError("Resource not found on GitHub (404).")
        if exc.code in (401, 403):
            raise ValueError("GitHub rejected the credentials for this request.")
        raise ValueError(f"GitHub request failed (HTTP {exc.code}).")
    except URLError:
        raise ValueError("GitHub is unreachable. Check your network connection and try again.")


# ── Repository content access ────────────────────────────────────────────────

def fetch_repo_tree(
    owner: str, repo: str, ref: str, access_token: Optional[str]
) -> List[Dict[str, Any]]:
    """Full file listing [{path, type, size, sha}] for a ref (recursive)."""
    data = _request_json(f"{API_ROOT}/repos/{owner}/{repo}/git/trees/{ref}?recursive=1", access_token)
    tree = data.get("tree", [])
    return [
        {
            "path": item.get("path", ""),
            "type": item.get("type", "blob"),
            "size": item.get("size", 0) or 0,
            "sha": item.get("sha", ""),
        }
        for item in tree
    ]


def fetch_blob(
    owner: str, repo: str, file_sha: str, access_token: Optional[str]
) -> Optional[str]:
    """Decode a file blob; returns None for oversized or binary content."""
    data = _request_json(f"{API_ROOT}/repos/{owner}/{repo}/git/blobs/{file_sha}", access_token)
    if data.get("encoding") != "base64":
        return None
    if (data.get("size") or 0) > MAX_BLOB_BYTES:
        return None
    import base64

    raw = base64.b64decode(data.get("content", "") or "")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def fetch_default_branch(owner: str, repo: str, access_token: Optional[str]) -> str:
    data = _request_json(f"{API_ROOT}/repos/{owner}/{repo}", access_token)
    return data.get("default_branch") or "main"


# ── Pull request helpers ─────────────────────────────────────────────────────

def fetch_pr_metadata(
    owner: str, repo: str, pull_number: int, access_token: Optional[str]
) -> Dict[str, Any]:
    return _request_json(f"{API_ROOT}/repos/{owner}/{repo}/pulls/{pull_number}", access_token)


def fetch_pr_diff(
    owner: str, repo: str, pull_number: int, access_token: Optional[str]
) -> str:
    from urllib.error import URLError
    from urllib.request import Request, urlopen

    from .github import MAX_DIFF_BYTES, _headers

    headers = _headers({"Accept": "application/vnd.github.v3.diff"}, access_token)
    request = Request(f"{API_ROOT}/repos/{owner}/{repo}/pulls/{pull_number}", headers=headers)
    try:
        with urlopen(request, timeout=20) as response:
            data = response.read(MAX_DIFF_BYTES + 1)
    except Exception:
        raise ValueError("GitHub could not download the pull request diff.")
    if len(data) > MAX_DIFF_BYTES:
        raise ValueError("The pull request diff is too large to review (>5 MB).")
    return data.decode("utf-8", errors="replace")


def post_pr_comment(
    owner: str,
    repo: str,
    pull_number: int,
    body: str,
    access_token: Optional[str],
) -> Optional[str]:
    """Post a review comment on a PR; returns the comment URL. Never raises."""
    if not access_token:
        logger.warning("No GitHub token available; skipping PR comment on %s/%s#%s",
                       owner, repo, pull_number)
        return None
    body = body[:6000]
    try:
        data = _request_json(
            f"{API_ROOT}/repos/{owner}/{repo}/issues/{pull_number}/comments",
            access_token,
            method="POST",
            body={"body": body},
        )
        return data.get("html_url")
    except ValueError as exc:
        logger.warning("PR comment failed on %s/%s#%s: %s", owner, repo, pull_number, exc)
        return None


# ── Webhooks ─────────────────────────────────────────────────────────────────

def verify_webhook_signature(payload_body: bytes, signature_header: str, secret: str) -> bool:
    """Validate X-Hub-Signature-256 (sha256=<hex>) with a constant-time compare."""
    if not secret or not signature_header:
        return False
    if len(payload_body) > WEBHOOK_MAX_BODY:
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), payload_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header.strip())


def parse_pull_request_event(payload: Dict[str, Any]) -> Optional[Tuple[str, str, int, str, str]]:
    """Extract (owner, repo, pr_number, action, head_sha) from a PR webhook event."""
    pr = payload.get("pull_request") or {}
    repo = payload.get("repository") or {}
    full_name = repo.get("full_name") or ""
    number = pr.get("number")
    head_sha = (pr.get("head") or {}).get("sha") or ""
    if not full_name or not isinstance(number, int):
        return None
    owner, _, name = full_name.partition("/")
    return owner, name, number, str(payload.get("action", "")), head_sha


def format_review_comment(
    review_title: str,
    summary: str,
    findings: List[Dict[str, Any]],
    max_findings: int = 10,
) -> str:
    """Markdown PR comment body for an automated CodeSentinal review."""
    lines = [f"## 🛡️ CodeSentinal Review — {review_title}", "", summary or "", ""]
    if not findings:
        lines.append("✅ **No issues found** by deterministic scanners or review agents.")
        return "\n".join(lines)
    order = {"High": 0, "Medium": 1, "Low": 2}
    ranked = sorted(findings, key=lambda f: order.get(f.get("severity", "Low"), 3))
    emoji = {"High": "🔴", "Medium": "🟠", "Low": "🟡"}
    for finding in ranked[:max_findings]:
        severity = finding.get("severity", "Low")
        where = finding.get("file_line") or finding.get("file") or "unknown"
        origin = finding.get("agent") or finding.get("scanner") or "scanner"
        corroborated = " · ✅ corroborated" if finding.get("corroborated") else ""
        lines.append(f"### {emoji.get(severity, '🟡')} [{severity}] {finding.get('title', 'Issue')}")
        lines.append(f"**Location:** `{where}` · **Source:** {origin}{corroborated}")
        if finding.get("description"):
            lines.append(f"\n{finding['description'][:800]}")
        if finding.get("fix_code"):
            lines.append("\n**Suggested fix:**")
            lines.append(f"```{finding.get('language') or ''}\n{finding['fix_code'][:1500]}\n```")
        lines.append("")
    if len(ranked) > max_findings:
        lines.append(f"_…and {len(ranked) - max_findings} more findings in the dashboard._")
    lines.append("---")
    lines.append("_Automated review by CodeSentinal. Findings are advisory — verify before merging._")
    return "\n".join(lines)
