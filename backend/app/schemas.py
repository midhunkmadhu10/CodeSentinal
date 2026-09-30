"""Pydantic request/response schemas for the SaaS API.

Legacy schemas (Finding, AnalyzeRequest, ...) keep their exact field names —
the current frontend and the existing test suite depend on them.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from .config import (
    MAX_DIFF_BYTES,
    MAX_GITHUB_TOKEN_CHARS,
    MAX_REPOSITORY_FIELD_CHARS,
    MAX_RULES_BYTES,
)
from .models import AnalyzeRequest, AnalyzeResponse, Finding, ScreeningSuggestion  # noqa: F401

__all__ = [
    "AnalyzeRequest", "AnalyzeResponse", "Finding", "ScreeningSuggestion",
    "RegisterRequest", "LoginAPIRequest", "TokenResponse", "UserOut",
    "RepositoryCreate", "RepositoryOut",
    "ReviewCreate", "ReviewFindingOut", "ReviewOut",
    "JobOut", "EvalOut",
    "GitHubImportRequest", "GitHubImportResponse",
]


# ── Auth ─────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=256)
    name: str = Field(default="", max_length=255)

    @field_validator("email")
    @classmethod
    def _email_shape(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("Enter a valid email address.")
        return value


class LoginAPIRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: str


# ── Repositories ─────────────────────────────────────────────────────────────

class RepositoryCreate(BaseModel):
    repository: str = Field(min_length=1, max_length=MAX_REPOSITORY_FIELD_CHARS)
    access_token: Optional[str] = Field(default=None, max_length=MAX_GITHUB_TOKEN_CHARS)

    @field_validator("repository")
    @classmethod
    def _repository_shape(cls, value: str) -> str:
        from .github import parse_repository

        try:
            owner, name = parse_repository(value)
        except ValueError as exc:
            raise ValueError(str(exc))
        return f"{owner}/{name}"


class RepositoryOut(BaseModel):
    id: int
    owner: str
    name: str
    full_name: str
    default_branch: str
    is_private: bool
    index_status: str
    indexed_at: Optional[str] = None
    chunk_count: int
    symbol_count: int
    file_count: int
    graph_nodes: int = 0
    graph_edges: int = 0
    last_error: Optional[str] = None
    created_at: Optional[str] = None


# ── Reviews ──────────────────────────────────────────────────────────────────

class ReviewCreate(BaseModel):
    diff: str = Field(min_length=1)
    rules: str = ""
    repository: str = Field(default="", max_length=400)
    title: str = Field(default="", max_length=500)
    repo_id: Optional[int] = None
    depth: str = Field(default="standard", pattern="^(standard|deep)$")

    @field_validator("diff")
    @classmethod
    def _diff_size(cls, value: str) -> str:
        size = len(value.encode("utf-8"))
        if size > MAX_DIFF_BYTES:
            raise ValueError(f"diff is too large ({size} bytes); the limit is {MAX_DIFF_BYTES} bytes.")
        return value

    @field_validator("rules")
    @classmethod
    def _rules_size(cls, value: str) -> str:
        size = len(value.encode("utf-8"))
        if size > MAX_RULES_BYTES:
            raise ValueError(f"rules is too large ({size} bytes); the limit is {MAX_RULES_BYTES} bytes.")
        return value


class ReviewFindingOut(BaseModel):
    id: int
    source: str
    agent: Optional[str] = None
    scanner: Optional[str] = None
    category: str
    severity: str
    file: str
    line: Optional[int] = None
    file_line: str
    title: str
    description: str
    rule: str
    cwe: str
    snippet: str
    fix_code: str
    tests: List[str] = Field(default_factory=list)
    confidence: Optional[float] = None
    corroborated: bool


class ReviewOut(BaseModel):
    id: int
    user_id: int
    repo_id: Optional[int] = None
    trigger: str
    repository: str
    title: str
    pr_number: Optional[int] = None
    status: str
    summary: str
    counts: Dict[str, Any]
    metrics: Dict[str, Any]
    created_at: Optional[str] = None
    finished_at: Optional[str] = None
    findings: List[ReviewFindingOut] = Field(default_factory=list)


# ── Jobs ─────────────────────────────────────────────────────────────────────

class JobOut(BaseModel):
    id: int
    type: str
    status: str
    payload: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    attempts: int
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class EvalOut(BaseModel):
    id: int
    created_at: Optional[str] = None
    scores: Dict[str, Any]
    details: Dict[str, Any]
    notes: str


# ── Legacy GitHub import ─────────────────────────────────────────────────────

class GitHubImportRequest(BaseModel):
    repository: str = Field(min_length=1, max_length=MAX_REPOSITORY_FIELD_CHARS)
    pull_number: Optional[int] = Field(default=None, ge=1, le=10_000_000)
    access_token: Optional[str] = Field(default=None, max_length=MAX_GITHUB_TOKEN_CHARS)


class GitHubImportResponse(BaseModel):
    repository: str
    diff: str = ""
    policy: Optional[str] = None
    policy_path: Optional[str] = None
    error: Optional[str] = None


TokenResponse.model_rebuild()
