# pyright: basic
# type: ignore

"""Pydantic models for Agent endpoints."""

from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    message: str


class AgentResponse(BaseModel):
    sandbox_id: str
    user_id: str
    message: str
    agent_reply: str
    success: bool = True
    code_outputs: list[dict] = Field(default_factory=list)
