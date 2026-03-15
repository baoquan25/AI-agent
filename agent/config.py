import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

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
    SANDBOX_API_URL: str 
    
    LLM_MODEL: str 
    REASONING_EFFORT: str 
    OPENAI_KEY: str


settings = Settings()
