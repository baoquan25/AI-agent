# pyright: basic
# type: ignore

"""
Application lifespan — initialise Daytona client and WorkspaceManager.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from daytona import Daytona, DaytonaConfig

from config import settings
from shared.workspace_manager import WorkspaceManager

logger = logging.getLogger("agent-api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        config = DaytonaConfig(
            api_key=settings.DAYTONA_API_KEY,
            api_url=settings.DAYTONA_API_URL,
        )
        daytona_client = Daytona(config)
        logger.info("Connected to Daytona API")
    except Exception as e:
        logger.error(f"Failed to connect to Daytona: {e}")
        daytona_client = None

    workspace_manager = WorkspaceManager(base_path="/home/daytona/workspace")

    app.state.daytona = daytona_client
    app.state.workspace_manager = workspace_manager
    app.state.user_sandboxes = {}
    app.state.user_lock = asyncio.Lock()

    yield

    logger.info("Agent API shutdown complete.")
