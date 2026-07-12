"""Small GitHub REST client for importing a PR diff and repository policy.

The access token is request-scoped: it is never written to disk or retained by
the application. GitHub URLs are parsed strictly to prevent arbitrary URL fetches.
"""

import base64
import json
import re
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


POLICY_PATHS = ("SECURITY.md", ".github/SECURITY.md", "SECURITY_POLICY.md")


def parse_repository(value: str) -> tuple[str, str]:
    value = value.strip()
    match = re.fullmatch(r"(?:https?://github\.com/)?([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?", value)
    if not match:
        raise ValueError("Enter a GitHub repository as owner/repository or https://github.com/owner/repository.")
    return match.group(1), match.group(2)


def _request_json(url: str, access_token: Optional[str]) -> dict:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "CodeSentinal"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token.strip()}"
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code in (401, 403, 404):
            raise ValueError("GitHub could not access that repository. Check the repository, pull request, and token permissions.")
        raise ValueError(f"GitHub request failed ({exc.code}).")
    except URLError:
        raise ValueError("GitHub is unavailable. Check your internet connection and try again.")


def _request_text(url: str, access_token: Optional[str]) -> str:
    headers = {"Accept": "application/vnd.github.v3.diff", "User-Agent": "CodeSentinal"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token.strip()}"
    try:
        with urlopen(Request(url, headers=headers), timeout=20) as response:
            return response.read().decode("utf-8")
    except HTTPError as exc:
        raise ValueError(f"GitHub could not download the diff ({exc.code}).")
    except URLError:
        raise ValueError("GitHub is unavailable. Check your internet connection and try again.")


def _load_policy(owner: str, repo: str, access_token: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    for path in POLICY_PATHS:
        try:
            data = _request_json(f"https://api.github.com/repos/{owner}/{repo}/contents/{path}", access_token)
        except ValueError:
            continue
        encoded = data.get("content", "")
        if encoded:
            return base64.b64decode(encoded).decode("utf-8", errors="replace"), path
    return None, None


def import_repository_review(repository: str, pull_number: Optional[int], access_token: Optional[str]) -> tuple[str, str, Optional[str], Optional[str]]:
    owner, repo = parse_repository(repository)
    base_url = f"https://api.github.com/repos/{owner}/{repo}"

    if pull_number:
        pull = _request_json(f"{base_url}/pulls/{pull_number}", access_token)
        diff = _request_text(f"{base_url}/pulls/{pull_number}", access_token)
    else:
        repo_data = _request_json(base_url, access_token)
        branch = repo_data.get("default_branch")
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
