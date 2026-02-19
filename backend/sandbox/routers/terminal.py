import asyncio
import json
import logging
import threading
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from daytona.common.pty import PtySize

from dependencies import get_sandbox
from models.terminal import CreatePtyRequest, ResizePtyRequest

logger = logging.getLogger("daytona-api")
router = APIRouter(prefix="/terminal", tags=["Terminal"])


def _session_to_dict(s):
    return {
        "id": getattr(s, "id", ""),
        "active": getattr(s, "active", False),
        "cols": getattr(s, "cols", 0),
        "rows": getattr(s, "rows", 0),
        "cwd": getattr(s, "cwd", ""),
        "created_at": getattr(s, "created_at", ""),
        "envs": getattr(s, "envs", None) or {},
    }


# ── REST API (theo Pseudo Terminal.md) ─────────────────────────────────────

@router.post("/pty")
async def create_pty_session(
    request: CreatePtyRequest,
    user_id: str = Header(default="default_user", alias="X-User-ID"),
    sb_and_id=Depends(get_sandbox),
):
    """Create PTY session (create_pty_session). Connect via WebSocket /terminal/pty?session_id={id}"""
    from daytona_toolbox_api_client.models import PtyCreateRequest as ApiPtyCreateRequest

    sandbox, sandbox_id = sb_and_id
    session_id = request.id or f"pty-{uuid.uuid4().hex[:12]}"
    envs = request.envs or {"TERM": "xterm-256color"}
    try:
        response = sandbox.process._api_client.create_pty_session(
            request=ApiPtyCreateRequest(
                id=session_id,
                cwd=request.cwd,
                envs=envs,
                cols=request.cols,
                rows=request.rows,
                lazy_start=True,
            ),
        )
        return {"success": True, "session_id": response.session_id, "sandbox_id": sandbox_id}
    except Exception as e:
        logger.error("Create PTY failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pty")
async def list_pty_sessions(
    user_id: str = Header(default="default_user", alias="X-User-ID"),
    sb_and_id=Depends(get_sandbox),
):
    """List all PTY sessions (list_pty_sessions)."""
    sandbox, sandbox_id = sb_and_id
    try:
        sessions = sandbox.process.list_pty_sessions()
        return {
            "success": True,
            "sandbox_id": sandbox_id,
            "sessions": [_session_to_dict(s) for s in sessions],
            "count": len(sessions),
        }
    except Exception as e:
        logger.error("List PTY failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}")
async def get_pty_session_info(
    session_id: str,
    user_id: str = Header(default="default_user", alias="X-User-ID"),
    sb_and_id=Depends(get_sandbox),
):
    """Get PTY session info (get_pty_session_info)."""
    sandbox, sandbox_id = sb_and_id
    try:
        info = sandbox.process.get_pty_session_info(session_id)
        return {
            "success": True,
            "sandbox_id": sandbox_id,
            "session": _session_to_dict(info),
        }
    except Exception as e:
        logger.error("Get PTY info failed: %s", e)
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/session/{session_id}")
async def kill_pty_session(
    session_id: str,
    user_id: str = Header(default="default_user", alias="X-User-ID"),
    sb_and_id=Depends(get_sandbox),
):
    """Kill PTY session (kill_pty_session)."""
    sandbox, sandbox_id = sb_and_id
    try:
        sandbox.process.kill_pty_session(session_id)
        return {"success": True, "sandbox_id": sandbox_id, "session_id": session_id, "message": "Session killed"}
    except Exception as e:
        logger.error("Kill PTY failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pty/{session_id}/resize")
async def resize_pty_session(
    session_id: str,
    request: ResizePtyRequest,
    user_id: str = Header(default="default_user", alias="X-User-ID"),
    sb_and_id=Depends(get_sandbox),
):
    """Resize PTY session (resize_pty_session)."""
    sandbox, sandbox_id = sb_and_id
    try:
        info = sandbox.process.resize_pty_session(
            session_id, PtySize(cols=request.cols, rows=request.rows)
        )
        return {
            "success": True,
            "sandbox_id": sandbox_id,
            "session": _session_to_dict(info),
        }
    except Exception as e:
        logger.error("Resize PTY failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── WebSocket ──────────────────────────────────────────────────────────────

@router.websocket("/pty")
async def pty_websocket(
    websocket: WebSocket,
    user_id: str = Query(default="default_user"),
    session_id: str | None = Query(default=None, description="Connect to existing session; omit to create new"),
):
    await websocket.accept()
    app = websocket.app
    user_sandboxes = app.state.user_sandboxes

    sandbox_info = user_sandboxes.get(user_id)
    if not sandbox_info:
        if not app.state.daytona:
            await websocket.close(code=4001)
            return
        try:
            from shared.dependencies import _create_sandbox
            from config import settings as _settings
            async with app.state.user_lock:
                sandbox_info = user_sandboxes.get(user_id)
                if not sandbox_info:
                    sandbox = _create_sandbox(app.state.daytona, _settings, user_id)
                    user_sandboxes[user_id] = {"sandbox": sandbox, "sandbox_id": sandbox.id}
                    sandbox_info = user_sandboxes[user_id]
        except Exception as e:
            logger.warning("Cannot create sandbox: %s", e)
            await websocket.close(code=4001)
            return

    sandbox = sandbox_info["sandbox"]
    sid = session_id or f"ws-pty-{uuid.uuid4().hex[:8]}"
    pty_handle = None
    loop = asyncio.get_event_loop()
    created_by_us = session_id is None

    try:
        if session_id:
            pty_handle = sandbox.process.connect_pty_session(session_id)
        else:
            pty_handle = sandbox.process.create_pty_session(
                id=sid,
                cwd="/home/daytona/workspace",
                envs={"TERM": "xterm-256color"},
                pty_size=PtySize(cols=220, rows=50),
            )
    except Exception as e:
        logger.error("PTY create failed: %s", e)
        await websocket.close(code=4002)
        return

    try:
        output_queue: asyncio.Queue = asyncio.Queue()

        def _read_pty():
            try:
                for data in pty_handle:
                    asyncio.run_coroutine_threadsafe(output_queue.put(data), loop)
            except Exception:
                pass
            finally:
                asyncio.run_coroutine_threadsafe(output_queue.put(None), loop)

        threading.Thread(target=_read_pty, daemon=True).start()

        async def _send_output():
            try:
                while True:
                    data = await output_queue.get()
                    if data is None:
                        break
                    try:
                        await websocket.send_bytes(data)
                    except Exception:
                        break
            except asyncio.CancelledError:
                pass

        async def _recv_input():
            try:
                while True:
                    try:
                        msg = await websocket.receive()
                        if msg["type"] == "websocket.disconnect":
                            break
                        if "bytes" in msg and msg["bytes"]:
                            pty_handle.send_input(msg["bytes"].decode("utf-8", errors="replace"))
                        elif "text" in msg and msg["text"]:
                            raw = msg["text"]
                            if raw.strip().startswith('{"type":"resize"'):
                                try:
                                    pkt = json.loads(raw)
                                    cols = int(pkt.get("cols", 80))
                                    rows = int(pkt.get("rows", 24))
                                    pty_handle.resize(PtySize(cols=cols, rows=rows))
                                except Exception:
                                    pass
                                continue
                            pty_handle.send_input(raw)
                    except WebSocketDisconnect:
                        break
                    except Exception:
                        break
            except asyncio.CancelledError:
                pass

        await asyncio.gather(_send_output(), _recv_input())
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception:
        logger.exception("PTY WebSocket error")
    finally:
        if pty_handle and created_by_us:
            try:
                pty_handle.kill()
            except Exception:
                pass
