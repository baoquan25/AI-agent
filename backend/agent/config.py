# pyright: basic
# type: ignore

import os
import logging

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv()


class Settings(BaseSettings):
    DAYTONA_API_KEY: str = Field(..., description="Daytona API key (required)")
    DAYTONA_API_URL: str = Field(..., description="Daytona API URL (required)")
    SNAPSHOT_NAME: str = Field(default="sandbox-daytona")
    AUTO_STOP_INTERVAL: int = Field(default=7200)
    LANGUAGE: str = Field(default="python")

    # OpenHands Agent
    LLM_MODEL: str = Field(default="openai/gpt-5-nano-2025-08-07")
    OPENAI_KEY: str = Field(..., description="OpenAI API key (required)")


settings = Settings()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent-api")
