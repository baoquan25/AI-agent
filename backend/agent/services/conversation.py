import json
import uuid
from datetime import datetime, timezone

from dependencies import WORKSPACE

# In-memory thread store
_threads: dict[str, dict] = {}
_SENTINEL = object()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_uuid(value: str | None) -> str:
    if value:
        try:
            uuid.UUID(value)
            return value
        except ValueError:
            pass
    return str(uuid.uuid4())


def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def strip_workspace(path: str) -> str:
    prefix = WORKSPACE.rstrip("/") + "/"
    if path.startswith(prefix):
        return path[len(prefix):]
    return path


def get_thread(thread_id: str) -> dict | None:
    return _threads.get(thread_id)


def create_thread(thread_id: str, metadata: dict) -> dict:
    safe_metadata = dict(metadata) if isinstance(metadata, dict) else {}
    thread = {
        "thread_id": thread_id,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "metadata": safe_metadata,
        "status": "idle",
        "values": {"messages": []},
    }
    _threads[thread_id] = thread
    return thread


def delete_thread(thread_id: str) -> None:
    _threads.pop(thread_id, None)

