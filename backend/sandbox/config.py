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

    # Cache
    FILE_CACHE_MAX_SIZE: int = Field(default=1000)
    FILE_CACHE_TTL_SECONDS: float = Field(default=300)

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sandbox-api")
