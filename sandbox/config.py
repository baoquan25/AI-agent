import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

DAYTONA_API_KEY = os.getenv("DAYTONA_API_KEY", "")
DAYTONA_API_URL = os.getenv("DAYTONA_API_URL", "")

SNAPSHOT_NAME = os.getenv("SNAPSHOT_NAME", "sandbox-daytona")
AUTO_STOP_INTERVAL = int(os.getenv("AUTO_STOP_INTERVAL", "7200"))
LANGUAGE = os.getenv("LANGUAGE", "python")

FILE_CACHE_MAX_SIZE = int(os.getenv("FILE_CACHE_MAX_SIZE", "1000"))
FILE_CACHE_TTL_SECONDS = float(os.getenv("FILE_CACHE_TTL_SECONDS", "300"))

_daytona_path = "/home/daytona/workspace"
_local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workspace")
_default_workspace = _daytona_path if os.path.isdir("/home/daytona") else _local_path
WORKSPACE_PATH = os.getenv("WORKSPACE_PATH", _default_workspace)
