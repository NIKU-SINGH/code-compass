from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from compass_core.package_version import installed_version
from compass_server.errors import register_error_handlers
from compass_server.routers.query import router as query_router
from compass_server.settings import server_settings
from compass_server.web_bundle import STATIC_DIR, has_bundled_ui

VERSION = installed_version()
"""The installed version of ``compass-code``, the package that ships this server."""

app = FastAPI(
    title="Code Compass API", description="Backend for the Code Compass visual knowledge graph."
)

# Registered first so CORS (added last, hence outermost) decorates 500 responses too.
register_error_handlers(app)

# Allow the web app's dev server (FRONTEND_URL) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[server_settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Basic health check route for the frontend to verify connection."""
    return {"status": "ok", "service": "Code Compass Core API", "version": VERSION}


app.include_router(query_router, prefix="/api")

# Mounted last so the API routes above take precedence over the UI's files.
if has_bundled_ui():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="web")
