# pyright: basic
# type: ignore

"""
Application lifespan — initialise Daytona client, WorkspaceManager, and FilesystemService.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from daytona import Daytona, DaytonaConfig

from config import settings
from shared.workspace_manager import WorkspaceManager
from services.filesystem_service import FilesystemService

logger = logging.getLogger("sandbox-api")


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
    filesystem_service = FilesystemService(workspace_manager)

    app.state.daytona = daytona_client
    app.state.workspace_manager = workspace_manager
    app.state.fs_agent = filesystem_service       # keep "fs_agent" key for backward compat with dependencies.py
    app.state.user_sandboxes = {}
    app.state.user_lock = asyncio.Lock()

    yield

    logger.info("Shutdown complete.")
