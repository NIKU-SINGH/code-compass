import os
from pathlib import Path
from typing import Tuple, Type

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

STAGE = os.environ.get("STAGE", None)


class Settings(BaseSettings):
    KUZU_DB_PATH: str = Field(default=".compass/graph.kuzu", description="Path to the KuzuDB graph database file")
    LLM_MODEL: str = Field(default="gpt-4o-mini", description="LLM model identifier passed to LiteLLM")
    LLM_API_KEY: str = Field(default="", description="API key for the configured LLM provider")
    REPO_ROOT: Path = Field(default=Path("."), description="Root path of the repository being analysed")

    API_HOST: str = Field(default="127.0.0.1", description="Host the FastAPI server binds to")
    API_PORT: int = Field(default=8000, description="Port the FastAPI server listens on")

    FRONTEND_HOST: str = Field(default="localhost", description="Host of the frontend dev server")
    FRONTEND_PORT: int = Field(default=5173, description="Port of the frontend dev server")

    @computed_field
    @property
    def FRONTEND_URL(self) -> str:
        return f"http://{self.FRONTEND_HOST}:{self.FRONTEND_PORT}"

    class Config:
        validate_assignment = True
        case_sensitive = True
        env_file = f".env.{STAGE}" if STAGE else ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @classmethod
    def settings_customise_sources(
        cls,
        _settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        if os.environ.get("STAGE", "").lower() == "production":
            return env_settings, init_settings, file_secret_settings

        return dotenv_settings, env_settings, init_settings, file_secret_settings


settings = Settings()
