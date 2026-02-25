# pyright: basic
# type: ignore

"""
Application lifespan — initialise Daytona client, WorkspaceManager, and FilesystemService.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from daytona import Daytona, DaytonaConfig

from config import DAYTONA_API_KEY, DAYTONA_API_URL
from workspace_manager import WorkspaceManager
from services.filesystem_service import FilesystemService

logger = logging.getLogger("sandbox-api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        config = DaytonaConfig(
            api_key=DAYTONA_API_KEY,
            api_url=DAYTONA_API_URL,
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
    app.state.filesystem_service = filesystem_service

    yield

