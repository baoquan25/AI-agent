# pyright: basic
# type: ignore

"""Agent-specific FastAPI dependencies."""

from config import settings
from shared.dependencies import get_daytona, get_workspace_manager, make_get_sandbox

get_sandbox = make_get_sandbox(settings)
