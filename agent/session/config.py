import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DAYTONA_API_KEY = os.getenv("DAYTONA_API_KEY", "")
DAYTONA_API_URL = os.getenv("DAYTONA_API_URL", "")
SNAPSHOT_NAME = os.getenv("SNAPSHOT_NAME", "daytonaio/sandbox:0.5.0-slim")
AUTO_STOP_INTERVAL = int(os.getenv("AUTO_STOP_INTERVAL", "7200"))