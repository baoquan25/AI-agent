# pyright: basic
# type: ignore

"""
Application lifespan — initialise Daytona client, WorkspaceManager, FilesystemService,
and the workspace file watcher.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from daytona import Daytona, DaytonaConfig

from config import DAYTONA_API_KEY, DAYTONA_API_URL
from workspace_manager import WorkspaceManager
from services.filesystem_service import FilesystemService
from services.file_watcher import WorkspaceCacheWatcher

logger = logging.getLogger("sandbox-api")

_WORKSPACE_PATH = "/home/daytona/workspace"


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        config = DaytonaConfig(
            api_key=DAYTONA_API_KEY,
            api_url=DAYTONA_API_URL,
        )
        daytona_client = Daytona(config)
    except Exception as e:
        logger.error(f"Failed to connect to Daytona: {e}")
        daytona_client = None

    workspace_manager = WorkspaceManager(base_path=_WORKSPACE_PATH)
    filesystem_service = FilesystemService(workspace_manager)

    app.state.daytona = daytona_client
    app.state.workspace_manager = workspace_manager
    app.state.filesystem_service = filesystem_service

    # Import the global cache from the router so the watcher can invalidate it.
    from routers.file_system import _file_cache
    watcher = WorkspaceCacheWatcher(_file_cache, _WORKSPACE_PATH)
    watcher.start(asyncio.get_event_loop())
    app.state.file_watcher = watcher

    yield

    watcher.stop()
