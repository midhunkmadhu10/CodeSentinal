from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str


class AnalyzeRequest(BaseModel):
    diff: str
    rules: str
    llm_endpoint: Optional[str] = None
    llm_model: Optional[str] = None
    llm_api_key: Optional[str] = None


class Finding(BaseModel):
    severity: str  # "High" | "Medium" | "Low"
    file_line: str
    risk: str
    rule_violation: str
    safer_code: str
    source_chunk: str


class ScreeningSuggestion(BaseModel):
    priority: str
    title: str
    action: str


class AnalyzeResponse(BaseModel):
    findings: list[Finding]
    screening_suggestions: list[ScreeningSuggestion] = []
    error: Optional[str] = None


class GitHubImportRequest(BaseModel):
    repository: str
    pull_number: Optional[int] = None
    access_token: Optional[str] = None


class GitHubImportResponse(BaseModel):
    repository: str
    diff: str
    policy: Optional[str] = None
    policy_path: Optional[str] = None
    error: Optional[str] = None
