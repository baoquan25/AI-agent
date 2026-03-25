import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from daytona import Daytona, DaytonaConfig

from config import settings
from workspace_manager import WorkspaceManager
from services.filesystem_service import FilesystemService
from services.file_watcher import WorkspaceCacheWatcher
from services.event_broadcaster import broadcaster

logger = logging.getLogger("sandbox-api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        config = DaytonaConfig(
            api_key=settings.DAYTONA_API_KEY,
            api_url=settings.DAYTONA_API_URL,
        )
        daytona_client = Daytona(config)
    except Exception as e:
        logger.error(f"Failed to connect to Daytona: {e}")
        daytona_client = None

    workspace_manager = WorkspaceManager()
    filesystem_service = FilesystemService(workspace_manager)

    app.state.daytona = daytona_client
    app.state.workspace_manager = workspace_manager
    app.state.filesystem_service = filesystem_service
    app.state.event_broadcaster = broadcaster

    from routers.file_system import _file_cache

    watcher = WorkspaceCacheWatcher(_file_cache, broadcaster=broadcaster)
    watcher.start(asyncio.get_event_loop())
    app.state.file_watcher = watcher

    yield

    watcher.stop()
