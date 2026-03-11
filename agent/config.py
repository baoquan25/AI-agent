# pyright: basic
# type: ignore

import os
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

# Load sub-service .env first (if exists), then root .env
_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_here)
load_dotenv(os.path.join(_here, ".env"))
load_dotenv(os.path.join(_root, ".env"))


class Settings(BaseSettings):
    DAYTONA_API_KEY: str
    DAYTONA_API_URL: str
    SNAPSHOT_NAME: str = "daytonaio/sandbox:0.5.0-slim"
    AUTO_STOP_INTERVAL: int = 7200
    LANGUAGE: str = "python"

    SANDBOX_API_URL: str = "http://localhost:8000"
    LLM_MODEL: str = "openai/gpt-5-nano-2025-08-07"
    REASONING_EFFORT: str = "low"

    OPENAI_KEY: str = Field(..., env="OPENAI_KEY")


settings = Settings()
