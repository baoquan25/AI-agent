# pyright: basic
# type: ignore

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="", tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    service: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="ok", service="agent")
