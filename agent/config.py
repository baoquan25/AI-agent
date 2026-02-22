import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DAYTONA_API_KEY = os.getenv("DAYTONA_API_KEY", "")
DAYTONA_API_URL = os.getenv("DAYTONA_API_URL", "")
