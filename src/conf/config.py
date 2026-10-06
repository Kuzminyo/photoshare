"""Application settings read from environment variables and the ``.env`` file."""
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All settings of the app; each field can be set by the env variable of the same name.

    ``JWT_SECRET_KEY`` is required, the rest have defaults for local development.
    """

    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/photoshare"

    jwt_secret_key: str  # required: a known key would let anyone forge tokens
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Cloudinary
    cloudinary_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    cloudinary_folder: str = "PhotoShare"

    max_upload_size_mb: int = 10
    max_tags_per_photo: int = 5

    # public base URL of the API, used in the links returned to clients;
    # on Render it is taken from RENDER_EXTERNAL_URL when BASE_URL is not set
    base_url: str = Field(
        "http://localhost:8000", validation_alias=AliasChoices("BASE_URL", "RENDER_EXTERNAL_URL", "base_url")
    )

    # comma separated list, e.g. "http://localhost:3000,http://127.0.0.1:5173"
    cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("database_url")
    @classmethod
    def use_psycopg2_driver(cls, value: str) -> str:
        """Accept ``postgres://`` and ``postgresql://`` URLs given by cloud platforms.

        :param value: The URL from the environment.
        :return: The URL with the ``postgresql+psycopg2://`` scheme.
        """
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg2://" + value[len(prefix):]
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        """Allowed CORS origins parsed from the comma separated ``CORS_ORIGINS``.

        :return: The list of origins without empty items.
        :rtype: list[str]
        """
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
