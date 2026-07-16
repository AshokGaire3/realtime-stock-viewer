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

    # Persistence
    database_url: str = "sqlite:///./stockviewer.db"

    # CORS (comma-separated origins)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
