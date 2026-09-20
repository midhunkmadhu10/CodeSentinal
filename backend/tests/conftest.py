"""Shared test setup: environment variables and an authenticated API client.

Tests never require real API keys or network access — external calls are
mocked at the module boundary.
"""

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("AUTH_USERNAME", "test-user")
os.environ.setdefault("AUTH_PASSWORD", "test-password")
os.environ.setdefault("AUTH_TOKEN", "test-token")
os.environ.setdefault("LLM_ENDPOINT", "https://llm.example.invalid/v1")
os.environ.setdefault("LLM_MODEL", "test-model")
os.environ.setdefault("LLM_API_KEY", "test-api-key")

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> TestClient:
    from main import app

    return TestClient(app)


@pytest.fixture()
def auth_headers():
    return {"Authorization": "Bearer test-token"}
