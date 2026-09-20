"""Pydantic model validation: severity enum, size limits, request constraints."""
import pytest
from pydantic import ValidationError

from app.models import (
    AnalyzeRequest,
    Finding,
    GitHubImportRequest,
    Severity,
)


def test_severity_enum_values():
    assert Severity.HIGH.value == "High"
    assert Severity.MEDIUM.value == "Medium"
    assert Severity.LOW.value == "Low"


def test_finding_accepts_valid_severity():
    finding = Finding(
        severity="High",
        file_line="src/auth.ts:42",
        risk="SQL injection",
        rule_violation="Rule 1",
        safer_code="SELECT * FROM users WHERE id = ?",
        source_chunk="chunk",
    )
    assert finding.severity is Severity.HIGH


def test_finding_rejects_invalid_severity():
    with pytest.raises(ValidationError):
        Finding(
            severity="Critical",
            file_line="a.ts:1",
            risk="r",
            rule_violation="v",
            safer_code="c",
            source_chunk="s",
        )


def test_analyze_request_rejects_empty_diff():
    with pytest.raises(ValidationError):
        AnalyzeRequest(diff="", rules="some rules")


def test_analyze_request_rejects_empty_rules():
    with pytest.raises(ValidationError):
        AnalyzeRequest(diff="diff --git a/x b/x", rules="")


def test_analyze_request_rejects_oversized_diff():
    with pytest.raises(ValidationError):
        AnalyzeRequest(diff="+" + "x" * (500 * 1024), rules="rules")


def test_analyze_request_rejects_oversized_rules():
    with pytest.raises(ValidationError):
        AnalyzeRequest(diff="diff", rules="x" * (1024 * 1024 + 1))


def test_analyze_request_multibyte_size_limit():
    with pytest.raises(ValidationError):
        AnalyzeRequest(diff="é" * (500 * 1024 // 2 + 1), rules="rules")


def test_github_import_rejects_invalid_pull_number():
    with pytest.raises(ValidationError):
        GitHubImportRequest(repository="owner/repo", pull_number=0)
    with pytest.raises(ValidationError):
        GitHubImportRequest(repository="owner/repo", pull_number=-5)


def test_github_import_rejects_empty_repository():
    with pytest.raises(ValidationError):
        GitHubImportRequest(repository="")
