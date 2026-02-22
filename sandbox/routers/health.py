from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from dependencies import get_sandbox

router = APIRouter(prefix="", tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    sandbox_id: Optional[str] = None


@router.get("/health", response_model=HealthResponse)
async def health_check(sb_and_id=Depends(get_sandbox)):
    sandbox, sandbox_id = sb_and_id
    return HealthResponse(status="ok", service="sandbox", sandbox_id=sandbox_id)
