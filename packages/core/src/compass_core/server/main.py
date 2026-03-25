"""FastAPI application setup & mounts static/."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from compass_core.server.routers import chat, repo

app = FastAPI(title="Code Compass")

app.include_router(chat.router, prefix="/api")
app.include_router(repo.router, prefix="/api")

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
