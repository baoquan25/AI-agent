# pyright: basic
# type: ignore

"""Pydantic models for Terminal/PTY endpoints."""

from typing import Optional

from pydantic import BaseModel


class CreatePtyRequest(BaseModel):
    """Create PTY session (create_pty_session)."""
    id: Optional[str] = None
    cwd: str = "/home/daytona/workspace"
    cols: int = 220
    rows: int = 50
    envs: Optional[dict[str, str]] = None


class ResizePtyRequest(BaseModel):
    """Resize PTY session (resize_pty_session)."""
    cols: int
    rows: int
