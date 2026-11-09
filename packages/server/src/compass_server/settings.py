"""Settings of the HTTP server: where it binds and which frontend may call it."""

from __future__ import annotations

from pydantic import Field, computed_field

from compass_core.settings import Settings


class ServerSettings(Settings):
    """Engine settings plus the server's own, from the same environment and ``.env``.

    Attributes:
        API_HOST: Host the FastAPI server binds to.
        API_PORT: Port the FastAPI server listens on.
        FRONTEND_HOST: Host of the frontend dev server.
        FRONTEND_PORT: Port of the frontend dev server.
        FRONTEND_URL: Origin allowed by CORS, built from the two fields above.

    Example:
        ``API_PORT=9000 compass serve`` gives ``ServerSettings().API_PORT == 9000``;
        the defaults give ``FRONTEND_URL == "http://localhost:3000"``.
    """

    API_HOST: str = Field(default="127.0.0.1", description="Host the FastAPI server binds to")
    API_PORT: int = Field(default=8000, description="Port the FastAPI server listens on")

    FRONTEND_HOST: str = Field(default="localhost", description="Host of the frontend dev server")
    FRONTEND_PORT: int = Field(default=3000, description="Port of the frontend dev server")

    @computed_field  # type: ignore[prop-decorator]  # known mypy/pydantic limitation: mypy flags any decorator stacked on @property before the pydantic plugin can special-case @computed_field
    @property
    def FRONTEND_URL(self) -> str:
        return f"http://{self.FRONTEND_HOST}:{self.FRONTEND_PORT}"


server_settings = ServerSettings()
