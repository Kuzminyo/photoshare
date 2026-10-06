import os

# must be set before the app (and its settings) is imported
os.environ["JWT_SECRET_KEY"] = "test-secret-key-only-for-pytest-0123456789"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["CLOUDINARY_NAME"] = "demo"
os.environ["CLOUDINARY_API_KEY"] = "key"
os.environ["CLOUDINARY_API_SECRET"] = "secret"
os.environ["BASE_URL"] = "http://testserver"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from src.database.db import get_db
from src.database.models import Base
from src.services import cloud

# SQLite in memory by default; set TEST_DATABASE_URL to run the same tests on PostgreSQL
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if TEST_DATABASE_URL:
    engine = create_engine(TEST_DATABASE_URL)
else:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 64


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def cloud_calls(monkeypatch):
    """Fake Cloudinary: records uploads and deletions."""
    calls = {"uploaded": [], "deleted": []}
    counter = iter(range(1, 10_000))

    def fake_upload(file, user_id):
        n = next(counter)
        public_id = f"PhotoShare/user_{user_id}/photo{n}"
        calls["uploaded"].append(public_id)
        return f"https://res.cloudinary.com/demo/image/upload/{public_id}.jpg", public_id

    monkeypatch.setattr(cloud, "upload_photo", fake_upload)
    monkeypatch.setattr(cloud, "delete_photo", lambda public_id: calls["deleted"].append(public_id))
    return calls


@pytest.fixture()
def client(db, cloud_calls):
    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def signup(client, username, password="secret123"):
    resp = client.post(
        "/api/auth/signup", json={"username": username, "email": f"{username}@example.com", "password": password}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def login(client, login_name, password="secret123"):
    resp = client.post("/api/auth/login", data={"username": login_name, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


def auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture()
def admin(client):
    """The first user, therefore an administrator."""
    user = signup(client, "admin")
    return {"user": user, "headers": auth(login(client, "admin"))}


@pytest.fixture()
def alice(client, admin):
    user = signup(client, "alice")
    return {"user": user, "headers": auth(login(client, "alice"))}


@pytest.fixture()
def bob(client, admin):
    user = signup(client, "bob")
    return {"user": user, "headers": auth(login(client, "bob"))}


@pytest.fixture()
def moderator(client, admin):
    user = signup(client, "moder")
    resp = client.patch(f"/api/users/{user['id']}/role", json={"role": "moderator"}, headers=admin["headers"])
    assert resp.status_code == 200
    return {"user": user, "headers": auth(login(client, "moder"))}


def upload(client, headers, description="A photo", tags=None, content=PNG_BYTES, content_type="image/png"):
    data = {"description": description} if description is not None else {}
    if tags is not None:
        data["tags"] = tags
    return client.post(
        "/api/photos", files={"file": ("photo.png", content, content_type)}, data=data, headers=headers
    )
