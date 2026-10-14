from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class Health(BaseModel):
    ok: bool


@router.get("/api/health")
async def health() -> Health:
    return Health(ok=True)
