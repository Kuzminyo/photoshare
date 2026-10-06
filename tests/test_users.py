from tests.conftest import login, upload


def test_me_and_update(client, alice, bob):
    resp = client.get("/api/users/me", headers=alice["headers"])
    assert resp.json()["email"] == "alice@example.com"

    resp = client.patch(
        "/api/users/me",
        json={"full_name": "Alice A.", "bio": "Photographer", "email": "NEW@example.com", "username": "alice2"},
        headers=alice["headers"],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert (body["full_name"], body["email"], body["username"]) == ("Alice A.", "new@example.com", "alice2")
    # the token is bound to the id, so it still works after renaming
    assert client.get("/api/users/me", headers=alice["headers"]).status_code == 200


def test_update_conflicts_and_password(client, alice, bob):
    assert client.patch("/api/users/me", json={"username": "bob"}, headers=alice["headers"]).status_code == 409
    assert client.patch("/api/users/me", json={"email": "bob@example.com"}, headers=alice["headers"]).status_code == 409
    assert client.patch("/api/users/me", json={"username": "me"}, headers=alice["headers"]).status_code == 422
    # own email / username again is fine
    resp = client.patch("/api/users/me", json={"email": "alice@example.com", "username": "alice"}, headers=alice["headers"])
    assert resp.status_code == 200

    assert client.patch("/api/users/me", json={"password": "newpass1"}, headers=alice["headers"]).status_code == 200
    assert client.post("/api/auth/login", data={"username": "alice", "password": "secret123"}).status_code == 401
    assert login(client, "alice", "newpass1")


def test_public_profile(client, alice, bob):
    upload(client, alice["headers"])
    photo = upload(client, alice["headers"]).json()
    client.post(f"/api/photos/{photo['id']}/comments", json={"text": "hi"}, headers=alice["headers"])

    resp = client.get("/api/users/alice")
    assert resp.status_code == 200
    body = resp.json()
    assert body["photos_count"] == 2
    assert body["comments_count"] == 1
    assert "email" not in body
    assert client.get("/api/users/nobody").status_code == 404


def test_admin_lists_users(client, admin, alice):
    resp = client.get("/api/users", headers=admin["headers"])
    assert [u["username"] for u in resp.json()] == ["admin", "alice"]
    assert client.get("/api/users", headers=alice["headers"]).status_code == 403


def test_ban_and_unban(client, admin, alice):
    alice_id = alice["user"]["id"]
    assert client.patch(f"/api/users/{alice_id}/ban", headers=alice["headers"]).status_code == 403

    resp = client.patch(f"/api/users/{alice_id}/ban", headers=admin["headers"])
    assert resp.json()["is_active"] is False
    # existing tokens stop working and login is refused
    assert client.get("/api/users/me", headers=alice["headers"]).status_code == 403
    assert client.post("/api/auth/login", data={"username": "alice", "password": "secret123"}).status_code == 403

    resp = client.patch(f"/api/users/{alice_id}/unban", headers=admin["headers"])
    assert resp.json()["is_active"] is True
    assert client.get("/api/users/me", headers=alice["headers"]).status_code == 200


def test_admin_cannot_change_self_or_missing_user(client, admin):
    admin_id = admin["user"]["id"]
    assert client.patch(f"/api/users/{admin_id}/ban", headers=admin["headers"]).status_code == 400
    assert client.patch("/api/users/999/ban", headers=admin["headers"]).status_code == 404
    assert client.patch(f"/api/users/{admin_id}/role", json={"role": "user"}, headers=admin["headers"]).status_code == 400


def test_change_role(client, admin, alice):
    resp = client.patch(f"/api/users/{alice['user']['id']}/role", json={"role": "moderator"}, headers=admin["headers"])
    assert resp.json()["role"] == "moderator"
    bad = client.patch(f"/api/users/{alice['user']['id']}/role", json={"role": "king"}, headers=admin["headers"])
    assert bad.status_code == 422
