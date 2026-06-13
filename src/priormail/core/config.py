"""Application settings, read from the environment and validated on startup.

The app must refuse to boot if config is invalid (CLAUDE.md §8). Settings are
loaded once and cached via :func:`get_settings`.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

HF_URI_PREFIX = "hf://"


class Settings(BaseSettings):
    """Environment-backed configuration.

    Only what the minimal classify slice needs. DB/auth/Gmail settings are
    added when those features land.
    """

    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Database (Supabase Postgres) ---
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/postgres",
        description="Async Postgres connection string (asyncpg driver).",
    )
    database_ssl: bool = Field(
        default=True,
        description="Require SSL for DB connection. Set DATABASE_SSL=false for local plain Postgres.",
    )
    database_pool_size: int = Field(
        default=5,
        description="SQLAlchemy pool_size. Keep low on Supabase free tier (60-connection cap).",
    )

    # --- ML model ---
    # HuggingFace URI in the form ``hf://{repo_id}/{version}`` (BACKEND_INTEGRATION_GUIDE §2).
    priority_model_uri: str = Field(default="hf://insanar/priormail-priority/v2.0")
    priority_model_revision: str = Field(default="main")
    # Phishing model URI (public). Use ``hf://owner/repo/version``.
    phishing_model_uri: str = Field(default="hf://faizhuda/priormail-phishing/v1.0")

    # --- App ---
    # NoDecode: take the raw env string (comma-separated) instead of JSON-decoding it;
    # the `_split_cors` validator below turns it into a list.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default=["http://localhost:3000", "http://localhost:5173"]
    )
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")

    @field_validator("priority_model_uri")
    @classmethod
    def _validate_priority_uri(cls, value: str) -> str:
        if not value.startswith(HF_URI_PREFIX):
            raise ValueError(
                f"priority_model_uri must start with {HF_URI_PREFIX!r} "
                f"(e.g. 'hf://insanar/priormail-priority/v2.0'); got {value!r}"
            )
        if not parse_hf_uri(value)[1]:
            raise ValueError(
                f"priority_model_uri must include a version subfolder, "
                f"e.g. 'hf://insanar/priormail-priority/v2.0'; got {value!r}"
            )
        return value

    @field_validator("phishing_model_uri")
    @classmethod
    def _validate_phishing_uri(cls, value: str) -> str:
        if not value.startswith(HF_URI_PREFIX):
            raise ValueError(
                f"phishing_model_uri must start with {HF_URI_PREFIX!r} (e.g. 'hf://faizhuda/priormail-phishing/v1.0'); got {value!r}"
            )
        if not parse_hf_uri(value)[1]:
            raise ValueError(
                f"phishing_model_uri must include a version subfolder, e.g. 'hf://faizhuda/priormail-phishing/v1.0'; got {value!r}"
            )
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, value: object) -> object:
        # Allow a comma-separated string from the env (CORS_ORIGINS=a,b).
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def priority_model_repo_id(self) -> str:
        """The HF repo id, e.g. ``insanar/priormail-priority``."""
        return parse_hf_uri(self.priority_model_uri)[0]

    @property
    def priority_model_version(self) -> str:
        """The version subfolder, e.g. ``v2.0``."""
        return parse_hf_uri(self.priority_model_uri)[1]

    @property
    def phishing_model_repo_id(self) -> str:
        """The HF repo id for the phishing model, e.g. ``faizhuda/priormail-phishing``."""
        return parse_hf_uri(self.phishing_model_uri)[0]

    @property
    def phishing_model_version(self) -> str:
        """The version subfolder for the phishing model, e.g. ``v1.0``."""
        return parse_hf_uri(self.phishing_model_uri)[1]


def parse_hf_uri(uri: str) -> tuple[str, str]:
    """Split ``hf://{owner}/{repo}/{version}`` into ``(repo_id, version)``.

    ``repo_id`` is ``{owner}/{repo}``; ``version`` is the trailing subfolder
    (empty string if absent).
    """
    path = uri.removeprefix(HF_URI_PREFIX).strip("/")
    parts = path.split("/")
    if len(parts) < 3:
        # owner/repo with no version subfolder.
        return "/".join(parts), ""
    repo_id = "/".join(parts[:2])
    version = "/".join(parts[2:])
    return repo_id, version


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance (constructed on first call)."""
    return Settings()
