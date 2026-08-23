from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from compass_core.server.routers.chat import router as chat_router
from compass_core.server.routers.repo import router as repo_router
from compass_core.settings import settings

app = FastAPI(
    title="Code Compass API", description="Backend for the Code Compass visual knowledge graph."
)

# Allow the Vite dev server (localhost:5173) to talk to FastAPI (localhost:8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Basic health check route for the frontend to verify connection."""
    return {"status": "ok", "service": "Code Compass Core API", "version": "0.1.0"}


# Include routers
app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(repo_router, prefix="/api", tags=["repo"])
