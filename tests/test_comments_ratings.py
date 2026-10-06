from datetime import datetime

from tests.conftest import upload


def test_comments_flow(client, admin, alice, bob, moderator):
    photo = upload(client, alice["headers"]).json()
    url = f"/api/photos/{photo['id']}/comments"

    resp = client.post(url, json={"text": "Nice!"}, headers=bob["headers"])
    assert resp.status_code == 201
    comment = resp.json()
    assert comment["user"]["username"] == "bob"
    assert comment["created_at"] and comment["updated_at"]
    client.post(url, json={"text": "Thanks"}, headers=alice["headers"])

    listed = client.get(url, headers=alice["headers"]).json()
    assert [c["text"] for c in listed] == ["Nice!", "Thanks"]
    assert client.get(f"/api/photos/{photo['id']}", headers=alice["headers"]).json()["comments_count"] == 2

    # only the author edits
    edited = client.put(f"/api/comments/{comment['id']}", json={"text": "Very nice!"}, headers=bob["headers"])
    assert edited.status_code == 200
    assert edited.json()["text"] == "Very nice!"
    assert datetime.fromisoformat(edited.json()["updated_at"]) >= datetime.fromisoformat(comment["created_at"])
    assert client.put(f"/api/comments/{comment['id']}", json={"text": "x"}, headers=alice["headers"]).status_code == 403
    assert client.put("/api/comments/999", json={"text": "x"}, headers=alice["headers"]).status_code == 404

    # users cannot delete, moderators and admins can
    assert client.delete(f"/api/comments/{comment['id']}", headers=bob["headers"]).status_code == 403
    assert client.delete(f"/api/comments/{comment['id']}", headers=moderator["headers"]).status_code == 204
    second = listed[1]["id"]
    assert client.delete(f"/api/comments/{second}", headers=admin["headers"]).status_code == 204
    assert client.delete(f"/api/comments/{second}", headers=admin["headers"]).status_code == 404
    assert client.get(url, headers=alice["headers"]).json() == []


def test_comment_validation_and_missing_photo(client, alice):
    photo = upload(client, alice["headers"]).json()
    assert client.post(f"/api/photos/{photo['id']}/comments", json={"text": ""}, headers=alice["headers"]).status_code == 422
    assert client.post("/api/photos/999/comments", json={"text": "hi"}, headers=alice["headers"]).status_code == 404
    assert client.get("/api/photos/999/comments", headers=alice["headers"]).status_code == 404


def test_ratings_rules(client, admin, alice, bob, moderator):
    photo = upload(client, alice["headers"]).json()
    url = f"/api/photos/{photo['id']}/ratings"

    assert client.post(url, json={"value": 5}, headers=alice["headers"]).status_code == 403  # own photo
    assert client.post(url, json={"value": 6}, headers=bob["headers"]).status_code == 422
    assert client.post(url, json={"value": 0}, headers=bob["headers"]).status_code == 422
    assert client.post(url, json={"value": 4}, headers=bob["headers"]).status_code == 201
    assert client.post(url, json={"value": 5}, headers=bob["headers"]).status_code == 409  # only once
    assert client.post(url, json={"value": 1}, headers=moderator["headers"]).status_code == 201
    assert client.post("/api/photos/999/ratings", json={"value": 3}, headers=bob["headers"]).status_code == 404

    body = client.get(f"/api/photos/{photo['id']}", headers=bob["headers"]).json()
    assert body["rating"] == 2.5
    assert body["ratings_count"] == 2


def test_staff_view_and_delete_ratings(client, admin, alice, bob, moderator):
    photo = upload(client, alice["headers"]).json()
    url = f"/api/photos/{photo['id']}/ratings"
    client.post(url, json={"value": 3}, headers=bob["headers"])

    assert client.get(url, headers=bob["headers"]).status_code == 403
    ratings = client.get(url, headers=moderator["headers"]).json()
    assert [(r["value"], r["user"]["username"]) for r in ratings] == [(3, "bob")]
    assert client.get("/api/photos/999/ratings", headers=admin["headers"]).status_code == 404

    rating_id = ratings[0]["id"]
    assert client.delete(f"/api/ratings/{rating_id}", headers=bob["headers"]).status_code == 403
    assert client.delete(f"/api/ratings/{rating_id}", headers=admin["headers"]).status_code == 204
    assert client.delete(f"/api/ratings/{rating_id}", headers=moderator["headers"]).status_code == 404
    # after deletion the user may rate again
    assert client.post(url, json={"value": 5}, headers=bob["headers"]).status_code == 201


def test_rating_race_is_reported_as_conflict(client, alice, bob, monkeypatch):
    from src.repository import ratings as repository_ratings

    photo = upload(client, alice["headers"]).json()
    url = f"/api/photos/{photo['id']}/ratings"
    client.post(url, json={"value": 3}, headers=bob["headers"])
    # pretend the check happened before the other request committed
    monkeypatch.setattr(repository_ratings, "get_user_rating", lambda *args: None)
    assert client.post(url, json={"value": 4}, headers=bob["headers"]).status_code == 409
