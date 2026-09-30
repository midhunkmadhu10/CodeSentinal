"""Shared test setup: environment variables and an authenticated API client.

Tests never require real API keys or network access — external calls are
mocked at the module boundary. The worker and any real database file are
disabled/isolated so tests are hermetic.
"""

import os
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("AUTH_USERNAME", "test-user")
os.environ.setdefault("AUTH_PASSWORD", "test-password")
os.environ.setdefault("AUTH_TOKEN", "test-token")
os.environ.setdefault("LLM_ENDPOINT", "https://llm.example.invalid/v1")
os.environ.setdefault("LLM_MODEL", "test-model")
os.environ.setdefault("LLM_API_KEY", "test-api-key")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-not-for-production")
os.environ.setdefault("WORKER_ENABLED", "false")
# Hermetic database: one disposable SQLite file per test session.
os.environ.setdefault(
    "DATABASE_URL", "sqlite:///" + os.path.join(tempfile.gettempdir(), "codesentinal-test.db")
)

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from main import app

    # Context manager runs the app lifespan (init_db + seed demo user).
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def auth_headers():
    return {"Authorization": "Bearer test-token"}
