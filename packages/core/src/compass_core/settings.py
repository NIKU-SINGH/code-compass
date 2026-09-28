import os
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

STAGE = os.environ.get("STAGE", None)


class Settings(BaseSettings):
    LADYBUG_DB_PATH: str = Field(
        default=".compass/graph.ladybug", description="Path to the LadybugDB graph database file"
    )
    REPO_ROOT: Path = Field(
        default=Path("."), description="Root path of the repository being analysed"
    )

    API_HOST: str = Field(default="127.0.0.1", description="Host the FastAPI server binds to")
    API_PORT: int = Field(default=8000, description="Port the FastAPI server listens on")

    FRONTEND_HOST: str = Field(default="localhost", description="Host of the frontend dev server")
    FRONTEND_PORT: int = Field(default=3000, description="Port of the frontend dev server")

    @computed_field  # type: ignore[prop-decorator]  # known mypy/pydantic limitation: mypy flags any decorator stacked on @property before the pydantic plugin can special-case @computed_field
    @property
    def FRONTEND_URL(self) -> str:
        return f"http://{self.FRONTEND_HOST}:{self.FRONTEND_PORT}"

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
