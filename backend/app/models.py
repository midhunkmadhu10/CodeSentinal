"""Pydantic request/response schemas with strict validation."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from .config import (
    MAX_DIFF_BYTES,
    MAX_GITHUB_TOKEN_CHARS,
    MAX_REPOSITORY_FIELD_CHARS,
    MAX_RULES_BYTES,
)


class Severity(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


def _validate_encoded_size(value: str, max_bytes: int, label: str) -> str:
    size = len(value.encode("utf-8"))
    if size > max_bytes:
        raise ValueError(
            f"{label} is too large ({size} bytes); the limit is {max_bytes} bytes."
        )
    return value


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class LoginResponse(BaseModel):
    token: str


class AnalyzeRequest(BaseModel):
    diff: str = Field(min_length=1)
    rules: str = Field(min_length=1)

    @field_validator("diff")
    @classmethod
    def _diff_size(cls, value: str) -> str:
        return _validate_encoded_size(value, MAX_DIFF_BYTES, "diff")

    @field_validator("rules")
    @classmethod
    def _rules_size(cls, value: str) -> str:
        return _validate_encoded_size(value, MAX_RULES_BYTES, "rules")


class Finding(BaseModel):
    severity: Severity
    file_line: str = Field(max_length=300)
    risk: str = Field(max_length=2000)
    rule_violation: str = Field(max_length=2000)
    safer_code: str = Field(max_length=4000)
    source_chunk: str = Field(max_length=4000)


class ScreeningSuggestion(BaseModel):
    priority: Severity
    title: str = Field(max_length=300)
    action: str = Field(max_length=2000)


class AnalyzeResponse(BaseModel):
    findings: list[Finding] = Field(default_factory=list)
    screening_suggestions: list[ScreeningSuggestion] = Field(default_factory=list)
    error: Optional[str] = None


class GitHubImportRequest(BaseModel):
    repository: str = Field(min_length=1, max_length=MAX_REPOSITORY_FIELD_CHARS)
    pull_number: Optional[int] = Field(default=None, ge=1, le=10_000_000)
    access_token: Optional[str] = Field(
        default=None, max_length=MAX_GITHUB_TOKEN_CHARS
    )


class GitHubImportResponse(BaseModel):
    repository: str
    diff: str = ""
    policy: Optional[str] = None
    policy_path: Optional[str] = None
    error: Optional[str] = None
