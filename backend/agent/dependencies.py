from daytona import Daytona, DaytonaConfig
from daytona_api_client import SandboxState
from config import settings

WORKSPACE = "/home/daytona/workspace"

daytona= Daytona(DaytonaConfig(
    api_key=settings.DAYTONA_API_KEY,
    api_url=settings.DAYTONA_API_URL,
))

def get_sandbox(sandbox_id: str):
    sandbox = daytona.get(sandbox_id)
    if sandbox.state == SandboxState.STARTED:
        return sandbox
    if sandbox.state in (SandboxState.STOPPED, SandboxState.STOPPING):
        daytona.start(sandbox)
        return sandbox

    return None
