import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

DAYTONA_API_KEY = os.getenv("DAYTONA_API_KEY", "")
DAYTONA_API_URL = os.getenv("DAYTONA_API_URL", "")

SNAPSHOT_NAME = os.getenv("SNAPSHOT_NAME", "sandbox-daytona")
AUTO_STOP_INTERVAL = os.getenv("AUTO_STOP_INTERVAL", "7200")
LANGUAGE = os.getenv("LANGUAGE", "python")

FILE_CACHE_MAX_SIZE = int(os.getenv("FILE_CACHE_MAX_SIZE", "1000"))
FILE_CACHE_TTL_SECONDS = float(os.getenv("FILE_CACHE_TTL_SECONDS", "300"))

