import os
from dotenv import load_dotenv

# Load from sub-service .env first (if exists), then fall back to root .env
_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_here)
load_dotenv(os.path.join(_here, ".env"))
load_dotenv(os.path.join(_root, ".env"))

DAYTONA_API_KEY = os.getenv("DAYTONA_API_KEY", "")
DAYTONA_API_URL = os.getenv("DAYTONA_API_URL", "")

SNAPSHOT_NAME = os.getenv("SNAPSHOT_NAME", "sandbox-daytona")
AUTO_STOP_INTERVAL = int(os.getenv("AUTO_STOP_INTERVAL", "7200"))
LANGUAGE = os.getenv("LANGUAGE", "python")

FILE_CACHE_MAX_SIZE = int(os.getenv("FILE_CACHE_MAX_SIZE", "1000"))
FILE_CACHE_TTL_SECONDS = float(os.getenv("FILE_CACHE_TTL_SECONDS", "300"))

