import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

STAGE = os.environ.get("STAGE", None)


class Settings(BaseSettings):
    """Engine settings, read from the environment and ``.env``.

    Adapters that need more settings (e.g. ``compass_server.settings.ServerSettings``)
    subclass this so they share the same sources and ``STAGE`` handling.

    Attributes:
        LADYBUG_DB_PATH: Explicit path to the graph database; when it does not exist,
            the index is found by walking up from the working directory.
        REPO_ROOT: Root path of the repository being analysed.
        QUERY_TIMEOUT_MS: Per-query timeout for graph queries, in milliseconds.

    Example:
        ``QUERY_TIMEOUT_MS=5000 compass ingest .`` gives
        ``Settings().QUERY_TIMEOUT_MS == 5000``.
    """

    LADYBUG_DB_PATH: str = Field(
        default=".compass/graph.ladybug", description="Path to the LadybugDB graph database file"
    )
    REPO_ROOT: Path = Field(
        default=Path("."), description="Root path of the repository being analysed"
    )

    QUERY_TIMEOUT_MS: int = Field(
        default=10_000, description="Per-query timeout in milliseconds for graph queries"
    )

    model_config = SettingsConfigDict(
        validate_assignment=True,
        case_sensitive=True,
        env_file=f".env.{STAGE}" if STAGE else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        _settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        if os.environ.get("STAGE", "").lower() == "production":
            return env_settings, init_settings, file_secret_settings

        return env_settings, dotenv_settings, init_settings, file_secret_settings


settings = Settings()
