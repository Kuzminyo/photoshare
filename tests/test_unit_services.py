import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from src.repository import tags as repository_tags
from src.repository import tokens as repository_tokens
from src.services import cloud, qr


class TestTags(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(
            repository_tags.normalize_tags([" Cat", "#cat", "", "  ", "Dog", "# dog "]), ["cat", "dog"]
        )

    def test_get_or_create_empty(self):
        self.assertEqual(repository_tags.get_or_create_tags([], db=None), [])


class TestCloud(unittest.TestCase):
    def test_params_default_crop(self):
        self.assertEqual(cloud.transformation_params({"width": 100}), {"width": 100, "crop": "fill"})
        self.assertEqual(
            cloud.transformation_params({"width": 100, "crop": "fit", "format": "png"}),
            {"width": 100, "crop": "fit"},
        )
        self.assertEqual(cloud.transformation_params({"angle": 90}), {"angle": 90})

    def test_build_url_format_only(self):
        url = cloud.build_transformed_url("PhotoShare/x", {"format": "webp"})
        self.assertTrue(url.endswith("PhotoShare/x.webp"))

    def test_upload_photo(self):
        with patch("cloudinary.uploader.upload", return_value={"secure_url": "https://u", "public_id": "p"}) as up:
            self.assertEqual(cloud.upload_photo(b"data", 7), ("https://u", "p"))
        self.assertTrue(up.call_args.kwargs["public_id"].startswith("PhotoShare/user_7/"))

    def test_delete_photo_ignores_errors(self):
        with patch("cloudinary.uploader.destroy", side_effect=RuntimeError("down")) as destroy:
            cloud.delete_photo("p")
        destroy.assert_called_once()

    def test_is_configured(self):
        self.assertTrue(cloud.is_configured())


class TestQr(unittest.TestCase):
    def test_png(self):
        self.assertTrue(qr.make_qr_png("https://example.com").startswith(b"\x89PNG"))


def test_blacklist_cleans_expired(db):
    from sqlalchemy import select

    from src.database.models import BlacklistedToken

    past = datetime.now(timezone.utc) - timedelta(hours=1)
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    repository_tokens.add_to_blacklist("old", past, db)
    repository_tokens.add_to_blacklist("new", future, db)
    repository_tokens.add_to_blacklist("new", future, db)  # twice is fine
    assert db.scalars(select(BlacklistedToken.jti)).all() == ["new"]
    assert repository_tokens.is_blacklisted("new", db)


def test_health_and_root(client, monkeypatch):
    assert client.get("/").json()["docs"] == "/docs"
    assert client.get("/api/healthchecker").json() == {"message": "OK"}

    from main import app
    from src.database.db import get_db

    class BrokenSession:
        def execute(self, *args):
            raise RuntimeError("db is down")

    app.dependency_overrides[get_db] = lambda: BrokenSession()
    assert client.get("/api/healthchecker").status_code == 503


def test_get_db_yields_and_closes_session():
    from sqlalchemy import text

    from src.database.db import get_db

    gen = get_db()
    session = next(gen)
    assert session.execute(text("SELECT 1")).scalar() == 1
    gen.close()


def test_database_url_scheme_is_normalized():
    from src.conf.config import Settings

    for url in ("postgres://u:p@h/db", "postgresql://u:p@h/db", "postgresql+psycopg2://u:p@h/db"):
        assert Settings(database_url=url).database_url == "postgresql+psycopg2://u:p@h/db"
    assert Settings(database_url="sqlite://").database_url == "sqlite://"


def test_base_url_falls_back_to_render_external_url(monkeypatch):
    from src.conf.config import Settings

    monkeypatch.delenv("BASE_URL", raising=False)
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://photoshare.onrender.com")
    assert Settings(_env_file=None).base_url == "https://photoshare.onrender.com"
    monkeypatch.setenv("BASE_URL", "https://custom.example")
    assert Settings(_env_file=None).base_url == "https://custom.example"
