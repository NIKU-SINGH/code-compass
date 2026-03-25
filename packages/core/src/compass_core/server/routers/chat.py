"""/api/chat endpoints (stateless for now)."""

from fastapi import APIRouter

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat():
    return {"message": "not implemented"}
