from datetime import timedelta

import jwt

from src.conf.config import settings
from src.services import auth as auth_service
from tests.conftest import auth, login, signup


def test_first_user_is_admin_others_are_users(client):
    first = signup(client, "first")
    second = signup(client, "second")
    assert first["role"] == "admin"
    assert second["role"] == "user"
    assert "password" not in first


def test_signup_conflicts_and_validation(client):
    signup(client, "alice")
    resp = client.post("/api/auth/signup", json={"username": "other", "email": "ALICE@example.com", "password": "secret123"})
    assert resp.status_code == 409
    resp = client.post("/api/auth/signup", json={"username": "alice", "email": "new@example.com", "password": "secret123"})
    assert resp.status_code == 409
    resp = client.post("/api/auth/signup", json={"username": "me", "email": "me@example.com", "password": "secret123"})
    assert resp.status_code == 422
    resp = client.post("/api/auth/signup", json={"username": "x", "email": "bad", "password": "1"})
    assert resp.status_code == 422


def test_login_by_email_or_username(client):
    signup(client, "Alice")
    assert login(client, "Alice")["token_type"] == "bearer"
    assert login(client, "alice")["access_token"]
    assert login(client, " ALICE@example.com ")["access_token"]


def test_usernames_differing_only_in_case_are_taken(client):
    signup(client, "Alice")
    resp = client.post("/api/auth/signup", json={"username": "alice", "email": "a2@example.com", "password": "secret123"})
    assert resp.status_code == 409
    assert client.get("/api/users/ALICE").json()["username"] == "Alice"


def test_login_wrong_credentials(client):
    signup(client, "alice")
    assert client.post("/api/auth/login", data={"username": "alice", "password": "wrong"}).status_code == 401
    assert client.post("/api/auth/login", data={"username": "nobody", "password": "x"}).status_code == 401


def test_protected_route_requires_valid_token(client):
    assert client.get("/api/users/me").status_code == 401
    assert client.get("/api/users/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_refresh_token_rotation(client):
    signup(client, "alice")
    tokens = login(client, "alice")
    resp = client.get("/api/auth/refresh_token", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
    assert resp.status_code == 200
    new_tokens = resp.json()
    assert client.get("/api/users/me", headers=auth(new_tokens)).status_code == 200
    # the used refresh token is revoked
    again = client.get("/api/auth/refresh_token", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
    assert again.status_code == 401
    # an access token is not a refresh token
    wrong = client.get("/api/auth/refresh_token", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert wrong.status_code == 401
    assert client.get("/api/auth/refresh_token").status_code == 401


def test_logout_blacklists_tokens(client):
    signup(client, "alice")
    tokens = login(client, "alice")
    resp = client.post("/api/auth/logout", json={"refresh_token": tokens["refresh_token"]}, headers=auth(tokens))
    assert resp.status_code == 200
    me = client.get("/api/users/me", headers=auth(tokens))
    assert me.status_code == 401
    assert me.json()["detail"] == "Token has been revoked"
    refresh = client.get("/api/auth/refresh_token", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
    assert refresh.status_code == 401
    # other sessions keep working
    assert client.get("/api/users/me", headers=auth(login(client, "alice"))).status_code == 200


def test_logout_without_body_and_with_bad_refresh(client):
    signup(client, "alice")
    signup(client, "bob")
    tokens = login(client, "alice")
    assert client.post("/api/auth/logout", headers=auth(tokens)).status_code == 200

    tokens = login(client, "alice")
    bob_tokens = login(client, "bob")
    resp = client.post("/api/auth/logout", json={"refresh_token": "garbage"}, headers=auth(tokens))
    assert resp.status_code == 200
    # someone else's refresh token is not revoked
    tokens = login(client, "alice")
    client.post("/api/auth/logout", json={"refresh_token": bob_tokens["refresh_token"]}, headers=auth(tokens))
    resp = client.get("/api/auth/refresh_token", headers={"Authorization": f"Bearer {bob_tokens['refresh_token']}"})
    assert resp.status_code == 200


def test_expired_token(client):
    signup(client, "alice")
    token = auth_service._create_token(1, auth_service.ACCESS_SCOPE, timedelta(seconds=-1))
    resp = client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Token has expired"


def test_token_of_deleted_user_and_bad_payload(client):
    token = auth_service.create_access_token(999)
    assert client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    bad = jwt.encode({"sub": "abc", "scope": "access_token", "jti": "1"}, settings.jwt_secret_key, algorithm="HS256")
    assert client.get("/api/users/me", headers={"Authorization": f"Bearer {bad}"}).status_code == 401


def test_password_hashing():
    hashed = auth_service.hash_password("secret123")
    assert auth_service.verify_password("secret123", hashed)
    assert not auth_service.verify_password("other", hashed)
