from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from compass_server.errors import register_error_handlers
from compass_server.routers.query import router as query_router
from compass_server.settings import server_settings

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
    return {"status": "ok", "service": "Code Compass Core API", "version": "0.1.0"}


app.include_router(query_router, prefix="/api")
