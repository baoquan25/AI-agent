# pyright: basic
# type: ignore

from daytona import Daytona, DaytonaConfig
from daytona_api_client import SandboxState
from daytona.common.errors import DaytonaError
from config import settings


WORKSPACE = "/home/daytona/workspace"
LABEL_KEY = "user-id"

daytona= Daytona(DaytonaConfig(
    api_key=settings.DAYTONA_API_KEY,
    api_url=settings.DAYTONA_API_URL,
))

def get_sandbox(user_id: str):
    sandbox = daytona.find_one(labels={LABEL_KEY: user_id})
    if sandbox.state == SandboxState.STARTED:
        return sandbox
    if sandbox.state in (SandboxState.STOPPED, SandboxState.STOPPING):
        daytona.start(sandbox)
        return sandbox

    return None
