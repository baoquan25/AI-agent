"""
routers/conversation.py — Phiên chat có lưu lịch sử (LangGraph checkpointer).
Tạo phiên → gửi message (stream) → lịch sử do LangGraph lưu theo thread_id.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from session.llm import get_thread_messages, llm_answer_with_thread

logger = logging.getLogger("routers.conversation")
router = APIRouter(prefix="/conversation", tags=["conversation"])

# Chỉ lưu conversation_id -> user_id (để list + kiểm tra quyền). Lịch sử chat do LangGraph checkpointer lưu.
_conversations: dict[str, dict[str, Any]] = {}


class ChatRequest(BaseModel):
    message: str


@router.post("/")
async def create_conversation(
    user_id: str = Header(default="default_user", alias="X-User-ID"),
):
    """Tạo phiên chat mới. Trả về conversation_id (dùng làm thread_id trong LangGraph)."""
    conversation_id = str(uuid.uuid4())
    _conversations[conversation_id] = {"user_id": user_id}
    return {"conversation_id": conversation_id}


@router.get("/")
async def list_conversations(
    user_id: str = Header(default="default_user", alias="X-User-ID"),
):
    """Danh sách conversation_id của user."""
    ids = [cid for cid, data in _conversations.items() if data["user_id"] == user_id]
    return {"conversation_ids": ids}


@router.get("/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    user_id: str = Header(default="default_user", alias="X-User-ID"),
):
    """Lấy lịch sử chat của phiên (từ LangGraph checkpointer)."""
    if conversation_id not in _conversations:
        _conversations[conversation_id] = {"user_id": user_id}
    if _conversations[conversation_id]["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Conversation belongs to another user")
    messages = get_thread_messages(conversation_id, user_id)
    return {"messages": messages}


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Xóa phiên (bỏ khỏi list). Thread state trong checkpointer vẫn còn đến khi restart."""
    if conversation_id not in _conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")
    del _conversations[conversation_id]
    return {"deleted": conversation_id}


@router.post("/{conversation_id}/chat")
async def chat(
    conversation_id: str,
    body: ChatRequest,
    user_id: str = Header(default="default_user", alias="X-User-ID"),
):
    """Gửi message vào phiên, stream trả lời. LangGraph tự lưu lịch sử theo thread_id."""
    if conversation_id not in _conversations:
        _conversations[conversation_id] = {"user_id": user_id}
    if _conversations[conversation_id]["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Conversation belongs to another user")

    async def stream():
        try:
            async for chunk in llm_answer_with_thread(
                body.message,
                user_id=user_id,
                thread_id=conversation_id,
            ):
                yield f"data: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"
            yield "event: done\ndata: {}\n\n"
        except Exception as exc:
            logger.exception("conversation chat error: %s", exc)
            yield f"event: error\ndata: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
            yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
