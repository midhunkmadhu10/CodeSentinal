"""Authentication behavior: login, token verification, fail-closed config."""


def test_login_success(client):
    resp = client.post(
        "/api/auth/login",
        json={"username": "test-user", "password": "test-password"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"token": "test-token"}


def test_login_wrong_password(client):
    resp = client.post(
        "/api/auth/login",
        json={"username": "test-user", "password": "wrong"},
    )
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post(
        "/api/auth/login",
        json={"username": "nobody", "password": "test-password"},
    )
    assert resp.status_code == 401


def test_login_missing_fields(client):
    resp = client.post("/api/auth/login", json={"username": "test-user"})
    assert resp.status_code == 422


def test_protected_route_without_token(client):
    resp = client.get("/api/demo/diff")
    assert resp.status_code == 401


def test_protected_route_with_invalid_token(client):
    resp = client.get("/api/demo/diff", headers={"Authorization": "Bearer bogus"})
    assert resp.status_code == 401


def test_protected_route_with_malformed_header(client):
    resp = client.get("/api/demo/diff", headers={"Authorization": "test-token"})
    assert resp.status_code == 401


def test_protected_route_with_valid_token(client, auth_headers):
    resp = client.get("/api/demo/diff", headers=auth_headers)
    assert resp.status_code == 200


def test_login_fails_closed_without_credentials(client, monkeypatch):
    monkeypatch.setenv("AUTH_USERNAME", "")
    monkeypatch.setenv("AUTH_PASSWORD", "")
    resp = client.post(
        "/api/auth/login",
        json={"username": "test-user", "password": "test-password"},
    )
    assert resp.status_code == 503


def test_token_verification_fails_closed_without_token(client, monkeypatch):
    monkeypatch.setenv("AUTH_TOKEN", "")
    resp = client.get("/api/demo/diff", headers={"Authorization": "Bearer test-token"})
    assert resp.status_code == 503


def test_health_is_public(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
