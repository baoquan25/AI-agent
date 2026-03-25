from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from events import lifespan
from routers.health import router as health_router
from routers.run import router as run_router
from routers.file_system import router as fs_router
from routers.terminal import router as terminal_router

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(run_router)
app.include_router(fs_router)
app.include_router(terminal_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
