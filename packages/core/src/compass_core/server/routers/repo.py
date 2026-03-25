"""/api/repo endpoints."""

from fastapi import APIRouter

router = APIRouter(tags=["repo"])


@router.get("/repo")
async def repo_info():
    return {"message": "not implemented"}
