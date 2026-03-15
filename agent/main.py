from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from routers.conversation import router as conversation_router

app = FastAPI(title="Daytona Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(conversation_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, ws="wsproto")
