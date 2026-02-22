import json
import asyncio
from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from llm import llm_answer

router = APIRouter(prefix="/agent", tags=["chat"])


class ChatRequest(BaseModel):
    message: str


@router.post("/chat")
async def chat(
    body: ChatRequest,
    user_id: str = Header(default="default_user", alias="X-User-ID"),
):
    async def stream():
        try:
            text = await llm_answer(body.message, user_id=user_id)
            for chunk in text:
                yield f"data: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.01)
            yield "event: done\ndata: {}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
            yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
