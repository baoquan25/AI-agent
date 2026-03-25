import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load from sub-service .env first (if exists), then fall back to root .env
_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_here)
load_dotenv(os.path.join(_here, ".env"))
load_dotenv(os.path.join(_root, ".env"))


class Settings(BaseSettings):
    DAYTONA_API_KEY: str 
    DAYTONA_API_URL: str 

    SNAPSHOT_NAME: str 
    AUTO_STOP_INTERVAL: int 
    LANGUAGE: str 

    FILE_CACHE_MAX_SIZE: int 
    FILE_CACHE_TTL_SECONDS: float 


settings = Settings()
