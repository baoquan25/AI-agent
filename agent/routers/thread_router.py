import asyncio
import logging
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from dependencies import get_sandbox, WORKSPACE
from services.llm import run_agent
from services.conversation import (
    _SENTINEL,
    now_iso, ensure_uuid, sse, strip_workspace,
    get_thread, create_thread, delete_thread,
)

logger = logging.getLogger("agent-api")

router = APIRouter(prefix="/conversation", tags=["Conversation"])


def _user_id(request: Request) -> str:
    return (
        request.headers.get("x-api-key")
        or request.headers.get("x-user-id")
        or "default_user"
    )


# ── POST /conversation/threads ───────────────────────────────────────────────

class ThreadCreateBody(BaseModel):
    metadata: dict = {}
    thread_id: str | None = None
    if_exists: str | None = None


@router.post("/threads")
async def create_thread_endpoint(body: ThreadCreateBody = ThreadCreateBody()):
    thread_id = ensure_uuid(body.thread_id)
    existing = get_thread(thread_id)
    if existing and body.if_exists != "raise":
        return existing
    return create_thread(thread_id, body.metadata)


# ── GET /conversation/threads/{id}/state ────────────────────────────────────

@router.get("/threads/{thread_id}/state")
async def get_thread_state(thread_id: str):
    thread = get_thread(thread_id)
    if not thread:
        return {"values": {"messages": []}, "next": [], "checkpoint": None}
    has_messages = bool(thread["values"].get("messages"))
    return {
        "values": thread["values"],
        "next": [],
        "checkpoint": {"thread_id": thread_id} if has_messages else None,
        "tasks": [],
    }


# ── POST /conversation/threads/{id}/history ──────────────────────────────────

@router.post("/threads/{thread_id}/history")
async def get_thread_history(thread_id: str):
    thread = get_thread(thread_id)
    if not thread or not thread["values"].get("messages"):
        return []
    return [{"values": thread["values"], "next": [], "checkpoint": {"thread_id": thread_id}, "tasks": []}]


# ── POST /conversation/threads/{id}/runs/stream ──────────────────────────────

@router.post("/threads/{thread_id}/runs/stream")
async def run_stream(thread_id: str, request: Request):
    try:
        uuid.UUID(thread_id)
    except ValueError:
        raise HTTPException(400, f"Invalid thread_id '{thread_id}': must be a valid UUID.")
    user_id = _user_id(request)

    body = await request.json()
    messages = (body.get("input") or {}).get("messages") or []
    human_text = next((m.get("content", "") for m in reversed(messages) if m.get("type") == "human"), None)
    if not human_text:
        raise HTTPException(400, "No human message in input")

    sandbox = get_sandbox(user_id)
    if sandbox is None:
        raise HTTPException(404, f"No sandbox found for user '{user_id}'. Please create a sandbox first.")

    try:
        sandbox.fs.create_folder(WORKSPACE, "755")
    except Exception:
        pass

    thread = get_thread(thread_id)
    if thread is None:
        thread = create_thread(thread_id, {})

    thread["values"]["messages"].append({
        "type": "human",
        "content": human_text,
        "id": f"msg-{uuid.uuid4().hex[:12]}",
    })

    execution_log: list[dict] = []
    file_edits: list[dict] = []

    async def event_stream():
        yield sse("metadata", {"run_id": str(uuid.uuid4())})

        loop = asyncio.get_event_loop()
        token_queue: asyncio.Queue = asyncio.Queue()
        ai_msg_id = f"msg-{uuid.uuid4().hex[:12]}"
        accumulated = ""

        def _run():
            try:
                reply = run_agent(sandbox, user_id, human_text,
                                  conversation_id=thread_id,
                                  token_queue=token_queue, loop=loop,
                                  execution_log=execution_log,
                                  file_edits=file_edits)
                loop.call_soon_threadsafe(token_queue.put_nowait, _SENTINEL)
                loop.call_soon_threadsafe(token_queue.put_nowait, {"ok": True, "reply": reply})
            except Exception as e:
                logger.exception("Agent execution failed")
                loop.call_soon_threadsafe(token_queue.put_nowait, _SENTINEL)
                loop.call_soon_threadsafe(token_queue.put_nowait, {"ok": False, "error": str(e)})

        loop.run_in_executor(None, _run)

        while True:
            item = await token_queue.get()
            if item is _SENTINEL:
                break
            if item.get("type") == "content":
                token_text = item["content"]
                accumulated += token_text
                yield sse("messages", [
                    {"type": "ai", "content": token_text, "id": ai_msg_id},
                    {},
                ])

        result = await token_queue.get()
        if not result["ok"]:
            accumulated = f"Error: {result['error']}"

        ai_msg = {"type": "ai", "content": accumulated, "id": ai_msg_id}
        thread["values"]["messages"].append(ai_msg)
        thread["updated_at"] = now_iso()

        if execution_log:
            thread["values"]["code_outputs"] = execution_log
        else:
            thread["values"].pop("code_outputs", None)

        if file_edits:
            thread["values"]["file_edits"] = [
                {**e, "path": strip_workspace(e["path"])} for e in file_edits
            ]
            thread["values"]["_file_edits_id"] = uuid.uuid4().hex[:12]
        else:
            thread["values"].pop("file_edits", None)
            thread["values"].pop("_file_edits_id", None)

        yield sse("values", thread["values"])
        yield "event: end\ndata: \"\"\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── DELETE /conversation/threads/{id} ───────────────────────────────────────

@router.delete("/threads/{thread_id}")
async def delete_thread_endpoint(thread_id: str):
    delete_thread(thread_id)
    return {"status": "ok"}
