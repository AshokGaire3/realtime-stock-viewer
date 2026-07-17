"""Application settings, loaded from environment / .env.

All upstream API keys live here (server-side only) so they are never bundled
into the frontend, which was the core security issue in the original app.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Upstream providers
    alpha_vantage_api_key: str = "demo"
    finnhub_api_key: str = ""

    # Claude API
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"

    # Persistence. Defaults to a local SQLite file for dev; production sets
    # DATABASE_URL to managed Postgres (a container filesystem is ephemeral, so
    # a SQLite file there is wiped on every deploy).
    database_url: str = "sqlite:///./stocklab.db"

    # CORS (comma-separated origins)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Optional regex for origins that can't be enumerated — Vercel gives every
    # preview deploy a fresh random *.vercel.app hostname.
    cors_origin_regex: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sqlalchemy_url(self) -> str:
        """DATABASE_URL normalised for SQLAlchemy.

        Render (and Heroku) hand out `postgres://` URLs, a scheme SQLAlchemy 2
        removed, so connecting with the raw value raises NoSuchModuleError.
        """
        url = self.database_url
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
