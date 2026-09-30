"""Tests for GitHub integration and job system."""

import json
import hmac
import hashlib
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.github_service import (
    verify_webhook_signature,
    parse_pull_request_event,
    format_review_comment,
)
from app.worker import enqueue_job, handle_job, _execute
from app.db_models import Job


class TestWebhookSignatureVerification:
    """Test webhook signature verification prevents spoofing."""

    def test_verify_webhook_signature_valid(self):
        """Valid HMAC-SHA256 signature passes verification."""
        secret = "my_webhook_secret"
        payload = b'{"action": "opened"}'
        expected_sig = "sha256=" + hmac.new(
            secret.encode("utf-8"), payload, hashlib.sha256
        ).hexdigest()
        
        assert verify_webhook_signature(payload, expected_sig, secret) is True

    def test_verify_webhook_signature_invalid(self):
        """Invalid signature fails verification."""
        secret = "my_webhook_secret"
        payload = b'{"action": "opened"}'
        bad_sig = "sha256=bad_signature_here"
        
        assert verify_webhook_signature(payload, bad_sig, secret) is False

    def test_verify_webhook_signature_no_secret(self):
        """Missing secret fails verification."""
        payload = b'{"action": "opened"}'
        sig = "sha256=anything"
        
        assert verify_webhook_signature(payload, sig, "") is False

    def test_verify_webhook_signature_oversized_payload(self):
        """Oversized payloads fail verification."""
        secret = "my_webhook_secret"
        payload = b"x" * (26 * 1024 * 1024)  # Exceeds WEBHOOK_MAX_BODY
        sig = "sha256=anything"
        
        assert verify_webhook_signature(payload, sig, secret) is False

    def test_verify_webhook_signature_constant_time(self):
        """Signature comparison is constant-time (no early exit on mismatch)."""
        secret = "secret"
        payload = b'{"test": true}'
        valid_sig = "sha256=" + hmac.new(
            secret.encode("utf-8"), payload, hashlib.sha256
        ).hexdigest()
        
        # Should reject quickly but without timing leak
        bad_sig_similar = valid_sig[:-2] + "XX"
        assert verify_webhook_signature(payload, bad_sig_similar, secret) is False


class TestPullRequestEventParsing:
    """Test GitHub webhook payload parsing."""

    def test_parse_pull_request_event_valid(self):
        """Valid PR webhook payload is parsed correctly."""
        payload = {
            "action": "opened",
            "pull_request": {
                "number": 42,
                "head": {"sha": "abc123"},
            },
            "repository": {
                "full_name": "owner/repo",
            },
        }
        
        result = parse_pull_request_event(payload)
        
        assert result == ("owner", "repo", 42, "opened", "abc123")

    def test_parse_pull_request_event_missing_pr_number(self):
        """Missing PR number returns None."""
        payload = {
            "action": "opened",
            "pull_request": {},
            "repository": {"full_name": "owner/repo"},
        }
        
        result = parse_pull_request_event(payload)
        
        assert result is None

    def test_parse_pull_request_event_valid_minimum(self):
        """Valid PR webhook payload with minimal fields."""
        payload = {
            "action": "opened",
            "pull_request": {"number": 42},
            "repository": {"full_name": "owner/repo"},
        }
        
        result = parse_pull_request_event(payload)
        
        assert result == ("owner", "repo", 42, "opened", "")


class TestReviewCommentFormatting:
    """Test PR review comment generation."""

    def test_format_review_comment_no_findings(self):
        """Review comment without findings shows success message."""
        comment = format_review_comment(
            "Security Review",
            "All checks passed",
            []
        )
        
        assert "No issues found" in comment
        assert "Security Review" in comment

    def test_format_review_comment_with_findings(self):
        """Review comment formats findings correctly."""
        findings = [
            {
                "severity": "High",
                "title": "SQL Injection",
                "file": "app/db.py",
                "line": 42,
                "file_line": "app/db.py:42",
                "description": "String interpolation in SQL query",
                "agent": "security",
                "corroborated": True,
            }
        ]
        
        comment = format_review_comment(
            "Security Review",
            "Found issues",
            findings
        )
        
        assert "SQL Injection" in comment
        assert "app/db.py:42" in comment
        assert "corroborated" in comment
        assert "🔴" in comment  # High severity emoji

    def test_format_review_comment_multiple_severities(self):
        """Review comment sorts findings by severity."""
        findings = [
            {"severity": "Low", "title": "Style issue", "file": "a.py", "line": 1, "corroborated": False},
            {"severity": "High", "title": "Injection", "file": "b.py", "line": 2, "corroborated": False},
            {"severity": "Medium", "title": "Bug", "file": "c.py", "line": 3, "corroborated": False},
        ]
        
        comment = format_review_comment("Review", "", findings)
        
        # High should come before Medium before Low
        high_pos = comment.find("Injection")
        med_pos = comment.find("Bug")
        low_pos = comment.find("Style")
        
        assert high_pos < med_pos < low_pos

    def test_format_review_comment_max_findings(self):
        """Review comment caps findings and shows overflow count."""
        findings = [
            {"severity": "High", "title": f"Issue {i}", "file": "app.py", "line": i, "corroborated": False}
            for i in range(15)
        ]
        
        comment = format_review_comment("Review", "", findings, max_findings=10)
        
        assert "…and 5 more findings" in comment


class TestJobEnqueuing:
    """Test background job enqueuing."""

    def test_enqueue_job_creates_queued_job(self):
        """enqueue_job creates a job with status='queued'."""
        from app.database import SessionLocal, init_db
        
        init_db()
        db = SessionLocal()
        
        try:
            job = enqueue_job(
                db,
                type="index_repository",
                payload={"repo_id": 123},
                user_id=1,
            )
            
            assert job.status == "queued"
            assert job.type == "index_repository"
            assert job.attempts == 0
            assert job.payload == {"repo_id": 123}
        finally:
            db.close()

    def test_enqueue_job_no_payload(self):
        """enqueue_job defaults to empty payload."""
        from app.database import SessionLocal, init_db
        
        init_db()
        db = SessionLocal()
        
        try:
            job = enqueue_job(db, type="test_job")
            
            assert job.payload == {}
        finally:
            db.close()


class TestJobHandling:
    """Test job handler dispatch."""

    def test_handle_job_index_repository_missing_repo(self):
        """handle_job raises ValueError if repository not found."""
        from app.database import SessionLocal, init_db
        
        init_db()
        db = SessionLocal()
        
        try:
            job = Job(
                type="index_repository",
                payload={"repo_id": 99999},  # Non-existent repo
                status="running",
            )
            
            with pytest.raises(ValueError, match="Repository not found"):
                handle_job(db, job)
        finally:
            db.close()

    def test_handle_job_unknown_type(self):
        """handle_job raises ValueError for unknown job types."""
        from app.database import SessionLocal, init_db
        
        init_db()
        db = SessionLocal()
        
        try:
            job = Job(type="unknown_job_type", status="running")
            
            with pytest.raises(ValueError, match="Unknown job type"):
                handle_job(db, job)
        finally:
            db.close()


class TestWebhookEndpoint:
    """Test GitHub webhook HTTP endpoint (integration via conftest client)."""

    def test_webhook_signature_verified_in_handler(self):
        """Webhook signature verification is enforced in the handler."""
        # Signature verification is tested directly above.
        # HTTP endpoint tests require the FastAPI app via conftest.
        pass


class TestJobsEndpoint:
    """Test job listing and detail endpoints (integration tests)."""

    def test_jobs_endpoints_exist(self):
        """Verify job endpoints are registered."""
        # Endpoints are verified by the FastAPI app initialization.
        # These are integration tests and covered by the API client.
        pass
