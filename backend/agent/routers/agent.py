# pyright: basic
# type: ignore

"""
Agent router — thin HTTP layer.
Delegates all logic to AgentService.
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, Header, HTTPException

from dependencies import get_sandbox, get_workspace_manager
from models.agent import AgentRequest, AgentResponse
from services.agent_service import AgentService

logger = logging.getLogger("agent-api")

router = APIRouter(prefix="/agent", tags=["Agent"])

_agent_service = AgentService()


@router.post("/chat", response_model=AgentResponse)
async def agent_chat(
    req: AgentRequest,
    user_id: str = Header(default="default_user", alias="X-User-ID"),
    sb_and_id=Depends(get_sandbox),
    wm=Depends(get_workspace_manager),
):
    sandbox, sandbox_id = sb_and_id

    await wm.initialize(sandbox)
    sandbox_workspace = wm.base_path

    try:
        result = await asyncio.to_thread(
            _agent_service.run_chat, sandbox, user_id, req.message, sandbox_workspace,
        )
    except Exception as e:
        logger.exception("Agent execution failed")
        raise HTTPException(status_code=500, detail=f"Agent failed: {str(e)}")

    return AgentResponse(
        sandbox_id=sandbox_id,
        user_id=user_id,
        message=req.message,
        agent_reply=result["agent_reply"],
        success=True,
        code_outputs=result.get("code_outputs", []),
    )
