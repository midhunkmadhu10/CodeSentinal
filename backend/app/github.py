"""Small GitHub REST client for importing a PR diff and repository policy.

The access token is request-scoped: it is never written to disk, logged, or
retained by the application. GitHub URLs are parsed strictly to prevent
arbitrary URL fetches, and all failures surface as ValueError with a
user-safe message.
"""

import base64
import json
import re
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

POLICY_PATHS = ("SECURITY.md", ".github/SECURITY.md", "SECURITY_POLICY.md")
MAX_DIFF_BYTES = 5 * 1024 * 1024  # refuse to buffer absurdly large diffs


def parse_repository(value: str) -> tuple[str, str]:
    value = value.strip()
    match = re.fullmatch(
        r"(?:https?://github\.com/)?([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?",
        value,
    )
    if not match:
        raise ValueError(
            "Enter a GitHub repository as owner/repository or https://github.com/owner/repository."
        )
    return match.group(1), match.group(2)


def _headers(extra: dict[str, str], access_token: Optional[str]) -> dict[str, str]:
    headers = {"User-Agent": "CodeSentinal", **extra}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token.strip()}"
    return headers


def _is_rate_limited(exc: HTTPError) -> bool:
    if exc.code != 403:
        return False
    remaining = exc.headers.get("X-RateLimit-Remaining") if exc.headers else None
    return remaining == "0"


def _request_json(url: str, access_token: Optional[str]) -> dict:
    headers = _headers({"Accept": "application/vnd.github+json"}, access_token)
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if _is_rate_limited(exc):
            raise ValueError(
                "GitHub API rate limit reached. Add an access token or wait before retrying."
            )
        if exc.code in (401, 403):
            raise ValueError(
                "GitHub rejected the credentials for that repository. "
                "Check that the token has read access to it."
            )
        if exc.code == 404:
            raise ValueError(
                "Repository or pull request not found. Check the owner, name, and PR number."
            )
        raise ValueError(f"GitHub request failed (HTTP {exc.code}).")
    except URLError:
        raise ValueError("GitHub is unreachable. Check your network connection and try again.")


def _request_text(url: str, access_token: Optional[str]) -> str:
    headers = _headers({"Accept": "application/vnd.github.v3.diff"}, access_token)
    try:
        with urlopen(Request(url, headers=headers), timeout=20) as response:
            data = response.read(MAX_DIFF_BYTES + 1)
    except HTTPError as exc:
        if _is_rate_limited(exc):
            raise ValueError("GitHub API rate limit reached. Try again later.")
        raise ValueError(f"GitHub could not download the diff (HTTP {exc.code}).")
    except URLError:
        raise ValueError("GitHub is unreachable. Check your network connection and try again.")
    if len(data) > MAX_DIFF_BYTES:
        raise ValueError(
            "The diff for this selection is too large to review (>5 MB). "
            "Pick a specific pull request instead."
        )
    return data.decode("utf-8", errors="replace")


def _load_policy(owner: str, repo: str, access_token: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    for path in POLICY_PATHS:
        try:
            data = _request_json(
                f"https://api.github.com/repos/{owner}/{repo}/contents/{path}", access_token
            )
        except ValueError:
            continue
        encoded = data.get("content", "")
        if encoded:
            return base64.b64decode(encoded).decode("utf-8", errors="replace"), path
    return None, None


def import_repository_review(
    repository: str, pull_number: Optional[int], access_token: Optional[str]
) -> tuple[str, str, Optional[str], Optional[str]]:
    owner, repo = parse_repository(repository)
    base_url = f"https://api.github.com/repos/{owner}/{repo}"

    if pull_number:
        _request_json(f"{base_url}/pulls/{pull_number}", access_token)
        diff = _request_text(f"{base_url}/pulls/{pull_number}", access_token)
    else:
        repo_data = _request_json(base_url, access_token)
        branch = repo_data.get("default_branch")
        if not branch:
            raise ValueError("Could not determine the default branch of that repository.")
        commits = _request_json(f"{base_url}/commits?sha={branch}&per_page=1", access_token)
        if not commits or not commits[0].get("parents"):
            raise ValueError("This repository needs at least two commits to create a comparison.")
        head = commits[0]["sha"]
        base = commits[0]["parents"][0]["sha"]
        diff = _request_text(f"{base_url}/compare/{base}...{head}", access_token)

    if not diff.strip():
        raise ValueError("GitHub returned an empty diff for this selection.")

    policy, policy_path = _load_policy(owner, repo, access_token)
    return f"{owner}/{repo}", diff, policy, policy_path
