"""Run with: py -m pytest BE/tests -q (after installing pytest httpx)."""
import os
import sys
from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest

# A private test database: never point tests at your local users.db.
TEST_DIR = tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(TEST_DIR.name, 'auth-test.db').as_posix()}"
os.environ["JWT_SECRET_KEY"] = "test-secret-not-for-production-" + "x" * 40
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402
from database import SessionLocal, engine  # noqa: E402
from Models.Users import User  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_database():
    """Close SQLite connections before deleting the temporary DB on Windows."""
    yield
    engine.dispose()
    TEST_DIR.cleanup()



def test_auth_workflow():
    with TestClient(app) as client:
        register = client.post("/auth/register", json={
            "username": "student123", "password": "Test@1234", "email": "STUDENT@example.com"
        })
        assert register.status_code == 201, register.text
        assert register.json()["role"] == "USER"
        assert register.json()["email"] == "student@example.com"

        assert client.post("/auth/register", json={
            "username": "student124", "password": "Test@1234", "email": "student@example.com"
        }).status_code == 409
        assert client.post("/auth/login", json={
            "login": "student123", "password": "wrong"
        }).status_code == 401

        login = client.post("/auth/login", json={
            "login": "STUDENT@EXAMPLE.COM", "password": "Test@1234", "remember_me": True
        })
        assert login.status_code == 200, login.text
        assert login.json()["access_token"]
        assert login.json()["refresh_token"]
        auth_header = {"Authorization": "Bearer " + login.json()["access_token"]}
        refresh = login.json()["refresh_token"]
        new_tokens = client.post("/auth/refresh", json={"refresh_token": refresh})
        assert new_tokens.status_code == 200, new_tokens.text
        assert new_tokens.json()["refresh_token"] != refresh

        assert client.post("/auth/logout", headers=auth_header, json={
            "refresh_token": new_tokens.json()["refresh_token"]
        }).status_code == 200
        assert client.post("/auth/refresh", json={
            "refresh_token": new_tokens.json()["refresh_token"]
        }).status_code == 401
        assert client.post("/auth/change-password", json={
            "current_password": "Test@1234", "new_password": "New@1234", "confirm_password": "New@1234"
        }).status_code == 401

        new_login = client.post("/auth/login", json={"login": "student123", "password": "Test@1234"})
        token = new_login.json()["access_token"]
        changed = client.post("/auth/change-password", headers={"Authorization": "Bearer " + token}, json={
            "current_password": "Test@1234", "new_password": "New@1234", "confirm_password": "New@1234"
        })
        assert changed.status_code == 200, changed.text
        assert client.post("/auth/login", json={"login": "student123", "password": "Test@1234"}).status_code == 401
        assert client.post("/auth/login", json={"login": "student123", "password": "New@1234"}).status_code == 200

        # Token is delivered by email in production, not returned from API.
        with patch("Services.PasswordService.secrets.token_urlsafe", return_value="test-only-reset-token"):
            assert client.post("/auth/forgot-password", json={"email": "student@example.com"}).status_code == 200
        assert client.post("/auth/forgot-password", json={"email": "unknown@example.com"}).status_code == 200
        reset = client.post("/auth/reset-password", json={
            "token": "test-only-reset-token", "new_password": "Reset@1234", "confirm_password": "Reset@1234"
        })
        assert reset.status_code == 200, reset.text
        assert client.post("/auth/reset-password", json={
            "token": "test-only-reset-token", "new_password": "Again@1234", "confirm_password": "Again@1234"
        }).status_code == 400
        assert client.post("/auth/login", json={"login": "student123", "password": "Reset@1234"}).status_code == 200


def test_errors_and_refresh_replay():
    with TestClient(app) as client:
        assert client.post("/auth/register", content='{"username"abc"}', headers={
            "Content-Type": "application/json"
        }).status_code == 400
        assert client.post("/auth/register", json={
            "username": "bad@name", "password": "Test@1234", "email": "name@example.com"
        }).status_code == 400
        first = client.post("/auth/register", json={
            "username": "replay123", "password": "Test@1234", "email": "replay@example.com"
        })
        assert first.status_code == 201
        login = client.post("/auth/login", json={
            "login": "replay123", "password": "Test@1234"
        })
        old = login.json()["refresh_token"]
        rotated = client.post("/auth/refresh", json={"refresh_token": old})
        assert rotated.status_code == 200
        new = rotated.json()["refresh_token"]
        assert client.post("/auth/refresh", json={"refresh_token": old}).status_code == 401
        # Replaying an old rotated refresh token revokes the whole family.
        assert client.post("/auth/refresh", json={"refresh_token": new}).status_code == 401
        assert client.post("/auth/logout", json={"refresh_token": new}).status_code == 401


def test_rate_limit_wrong_password():
    with TestClient(app) as client:
        register = client.post("/auth/register", json={
            "username": "limited123", "password": "Test@1234", "email": "limited@example.com"
        })
        assert register.status_code == 201
        for _ in range(5):
            assert client.post("/auth/login", json={
                "login": "limited123", "password": "Wrong@1234"
            }).status_code == 401
        assert client.post("/auth/login", json={
            "login": "limited123", "password": "Wrong@1234"
        }).status_code == 429


def test_invalid_bearer_and_admin_permissions():
    from fastapi import Depends
    from Services.AuthDependencies import get_current_user, require_admin
    from Services.JWTService import JWTService

    # Test-only endpoints; they are never added to production main.py.
    if not any(getattr(route, "path", None) == "/_test/protected" for route in app.routes):
        app.add_api_route("/_test/protected", lambda user=Depends(get_current_user): {"id": user.id})
        app.add_api_route("/_test/admin", lambda user=Depends(require_admin): {"id": user.id})
    with TestClient(app) as client:
        r = client.post("/auth/register", json={
            "username": "role123", "password": "Test@1234", "email": "role@example.com"
        })
        assert r.status_code == 201
        assert client.get("/_test/protected").status_code == 401
        assert client.get("/_test/protected", headers={"Authorization": "Bearer xyz"}).status_code == 401
        login = client.post("/auth/login", json={"login": "role123", "password": "Test@1234"})
        token = login.json()["access_token"]
        headers = {"Authorization": "Bearer " + token}
        assert client.get("/_test/protected", headers=headers).status_code == 200
        assert client.get("/_test/admin", headers=headers).status_code == 403


def test_reset_revokes_refresh():
    with TestClient(app) as client:
        r = client.post("/auth/register", json={
            "username": "reset123", "password": "Test@1234", "email": "reset@example.com"
        })
        assert r.status_code == 201
        first = client.post("/auth/login", json={"login": "reset123", "password": "Test@1234"}).json()
        with patch("Services.PasswordService.secrets.token_urlsafe", return_value="test-reset-once-token"):
            assert client.post("/auth/forgot-password", json={"email": "reset@example.com"}).status_code == 200
        done = client.post("/auth/reset-password", json={
            "token": "test-reset-once-token", "new_password": "NewReset@1234", "confirm_password": "NewReset@1234"
        })
        assert done.status_code == 200, done.text
        assert client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]}).status_code == 401
