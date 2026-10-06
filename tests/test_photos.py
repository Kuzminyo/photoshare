from datetime import datetime, timedelta, timezone

from src.conf.config import settings
from src.services import cloud
from tests.conftest import upload


def test_upload_with_tags(client, alice, cloud_calls):
    resp = upload(client, alice["headers"], description="Sunset", tags=["Sea", "#sunset, sea", " beach "])
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["description"] == "Sunset"
    assert body["tags"] == ["beach", "sea", "sunset"]
    assert body["owner"]["username"] == "alice"
    assert body["rating"] is None and body["ratings_count"] == 0
    assert body["url"].startswith("https://res.cloudinary.com/")
    assert len(cloud_calls["uploaded"]) == 1


def test_tags_are_unique_for_the_app(client, alice, bob, db):
    from sqlalchemy import func, select

    from src.database.models import Tag

    upload(client, alice["headers"], tags=["cat"])
    upload(client, bob["headers"], tags=["cat", "dog"])
    assert db.scalar(select(func.count(Tag.id))) == 2


def test_upload_without_description_and_tags(client, alice):
    resp = upload(client, alice["headers"], description=None)
    assert resp.status_code == 201
    assert resp.json()["tags"] == []
    assert resp.json()["description"] is None


def test_upload_validation(client, alice, monkeypatch):
    assert upload(client, alice["headers"], tags=["a", "b", "c", "d", "e", "f"]).status_code == 422
    assert upload(client, alice["headers"], tags=["x" * 51]).status_code == 422
    assert upload(client, alice["headers"], content=b"text", content_type="text/plain").status_code == 415
    assert upload(client, alice["headers"], content=b"").status_code == 422

    monkeypatch.setattr(settings, "max_upload_size_mb", 0)
    assert upload(client, alice["headers"]).status_code == 413


def test_upload_when_cloudinary_fails(client, alice, monkeypatch):
    def broken(file, user_id):
        raise RuntimeError("cloudinary is down")

    monkeypatch.setattr(cloud, "upload_photo", broken)
    assert upload(client, alice["headers"]).status_code == 503

    monkeypatch.setattr(settings, "cloudinary_name", "")
    assert upload(client, alice["headers"]).status_code == 503


def test_upload_requires_auth(client, admin):
    assert upload(client, {}).status_code == 401


def test_get_photo(client, alice, bob):
    photo = upload(client, alice["headers"]).json()
    resp = client.get(f"/api/photos/{photo['id']}", headers=bob["headers"])
    assert resp.status_code == 200
    assert resp.json()["id"] == photo["id"]
    assert client.get("/api/photos/999", headers=bob["headers"]).status_code == 404


def test_update_photo_by_owner_and_admin(client, admin, alice, bob):
    photo = upload(client, alice["headers"], tags=["old"]).json()
    url = f"/api/photos/{photo['id']}"

    resp = client.put(url, json={"description": "New text"}, headers=alice["headers"])
    assert resp.status_code == 200
    assert resp.json()["description"] == "New text"
    assert resp.json()["tags"] == ["old"]  # tags not given -> kept

    resp = client.put(url, json={"description": "By admin", "tags": ["a", "b"]}, headers=admin["headers"])
    assert resp.json()["tags"] == ["a", "b"]

    assert client.put(url, json={"description": "hack"}, headers=bob["headers"]).status_code == 403
    assert client.put("/api/photos/999", json={"description": "x"}, headers=bob["headers"]).status_code == 404


def test_delete_photo(client, admin, alice, bob, cloud_calls):
    first = upload(client, alice["headers"]).json()
    second = upload(client, alice["headers"]).json()
    client.post(f"/api/photos/{first['id']}/comments", json={"text": "nice"}, headers=bob["headers"])
    client.post(f"/api/photos/{first['id']}/ratings", json={"value": 5}, headers=bob["headers"])

    assert client.delete(f"/api/photos/{first['id']}", headers=bob["headers"]).status_code == 403
    assert client.delete(f"/api/photos/{first['id']}", headers=alice["headers"]).status_code == 204
    assert client.get(f"/api/photos/{first['id']}", headers=alice["headers"]).status_code == 404
    assert client.delete(f"/api/photos/{second['id']}", headers=admin["headers"]).status_code == 204
    assert len(cloud_calls["deleted"]) == 2


def test_transform_and_qr(client, alice, bob):
    photo = upload(client, alice["headers"]).json()
    body = {"width": 300, "height": 300, "effect": "sepia", "radius": "max", "format": "png"}
    resp = client.post(f"/api/photos/{photo['id']}/transform", json=body, headers=alice["headers"])
    assert resp.status_code == 201, resp.text
    link = resp.json()
    assert "c_fill" in link["url"] and "e_sepia" in link["url"] and "r_max" in link["url"]
    assert link["url"].endswith(".png")
    assert link["transformation"] == "effect=sepia, format=png, height=300, radius=max, width=300"
    assert link["qr_code_url"].startswith("http://testserver/api/links/")

    token = link["qr_code_url"].split("/")[-2]
    qr = client.get(f"/api/links/{token}/qr")  # public, no auth
    assert qr.status_code == 200
    assert qr.headers["content-type"] == "image/png"
    assert qr.content.startswith(b"\x89PNG")

    redirect = client.get(f"/api/links/{token}", follow_redirects=False)
    assert redirect.status_code == 307
    assert redirect.headers["location"] == link["url"]

    links = client.get(f"/api/photos/{photo['id']}/links", headers=alice["headers"]).json()
    assert [item["id"] for item in links] == [link["id"]]

    assert client.post(f"/api/photos/{photo['id']}/transform", json=body, headers=bob["headers"]).status_code == 403
    assert client.get(f"/api/photos/{photo['id']}/links", headers=bob["headers"]).status_code == 403


def test_transform_validation_and_missing_link(client, alice):
    photo = upload(client, alice["headers"]).json()
    url = f"/api/photos/{photo['id']}/transform"
    assert client.post(url, json={}, headers=alice["headers"]).status_code == 422
    assert client.post(url, json={"effect": "explode"}, headers=alice["headers"]).status_code == 422
    assert client.post(url, json={"radius": -1}, headers=alice["headers"]).status_code == 422
    assert client.post(url, json={"angle": 90}, headers=alice["headers"]).status_code == 201
    assert client.get("/api/links/unknown/qr").status_code == 404
    assert client.get("/api/links/unknown", follow_redirects=False).status_code == 404


def _rate(client, photo_id, value, headers):
    assert client.post(f"/api/photos/{photo_id}/ratings", json={"value": value}, headers=headers).status_code == 201


def test_search_and_filters(client, admin, alice, bob, moderator):
    sea = upload(client, alice["headers"], description="Calm sea at night", tags=["sea"]).json()
    cat = upload(client, alice["headers"], description="My cat", tags=["cat", "pets"]).json()
    dog = upload(client, bob["headers"], description="Dog in the park", tags=["pets"]).json()
    _rate(client, sea["id"], 5, bob["headers"])
    _rate(client, cat["id"], 2, bob["headers"])
    _rate(client, dog["id"], 4, alice["headers"])

    def search(params, headers=alice["headers"]):
        resp = client.get("/api/photos", params=params, headers=headers)
        assert resp.status_code == 200, resp.text
        return resp.json()

    assert search({})["total"] == 3
    assert [p["id"] for p in search({"keyword": "SEA"})["items"]] == [sea["id"]]
    assert {p["id"] for p in search({"keyword": "pet"})["items"]} == {cat["id"], dog["id"]}  # found by tag name
    assert {p["id"] for p in search({"tag": "#Pets"})["items"]} == {cat["id"], dog["id"]}
    assert [p["id"] for p in search({"sort_by": "rating"})["items"]] == [sea["id"], dog["id"], cat["id"]]
    assert [p["id"] for p in search({"sort_by": "rating", "order": "asc"})["items"]] == [cat["id"], dog["id"], sea["id"]]
    assert [p["id"] for p in search({"order": "asc"})["items"]] == [sea["id"], cat["id"], dog["id"]]
    assert {p["id"] for p in search({"min_rating": 4})["items"]} == {sea["id"], dog["id"]}
    assert search({"keyword": "100%_"})["total"] == 0

    page = search({"limit": 1, "skip": 1})
    assert page["total"] == 3 and len(page["items"]) == 1

    now = datetime.now(timezone.utc)
    assert search({"date_from": (now - timedelta(hours=1)).isoformat()})["total"] == 3
    assert search({"date_to": (now - timedelta(days=1)).isoformat()})["total"] == 0

    top = search({"tag": "sea"})["items"][0]
    assert top["rating"] == 5.0 and top["ratings_count"] == 1


def test_search_by_user_only_for_staff(client, admin, alice, bob, moderator):
    upload(client, alice["headers"])
    upload(client, bob["headers"])
    assert client.get("/api/photos", params={"username": "alice"}, headers=alice["headers"]).status_code == 403

    for staff in (moderator, admin):
        resp = client.get("/api/photos", params={"username": "alice"}, headers=staff["headers"])
        assert resp.status_code == 200
        assert [p["owner"]["username"] for p in resp.json()["items"]] == ["alice"]
    resp = client.get("/api/photos", params={"username": "ghost"}, headers=admin["headers"])
    assert resp.json() == {"items": [], "total": 0, "skip": 0, "limit": 20}
