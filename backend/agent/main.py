# pyright: basic
# type: ignore

import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
sys.path.insert(0, str(_here))               # agent/ → from models import ...
sys.path.insert(0, str(_here.parent))        # backend/ → from shared import ...

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from events import lifespan
from routers.health import router as health_router
from routers.agent import router as agent_router

app = FastAPI(title="Daytona Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(agent_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001)
