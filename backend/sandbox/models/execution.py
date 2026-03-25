# pyright: basic
# type: ignore

"""Pydantic models for Code Execution endpoints."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class RunCodeRequest(BaseModel):
    code: str
    timeout: int = 30
    use_jupyter: bool = True
    file_path: Optional[str] = None


class OutputItem(BaseModel):
    type: str
    data: Any
    library: Optional[str] = None


class RunCodeResponse(BaseModel):
    output: str
    exit_code: int
    sandbox_id: str
    success: bool = True
    outputs: list[OutputItem] = Field(default_factory=list)
