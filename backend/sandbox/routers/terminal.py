import asyncio
import json
import logging
import threading
import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from daytona.common.pty import PtySize

from dependencies import resolve_sandbox

logger = logging.getLogger("daytona-api")
router = APIRouter(prefix="/terminal", tags=["Terminal"])
_PTY_OUTPUT_QUEUE_MAX = 1024


@router.websocket("/pty")
async def pty_websocket(
    websocket: WebSocket,
    user_id: str = Query(default="default_user"),
):
    await websocket.accept()
    try:
        sandbox, _ = await resolve_sandbox(websocket.app.state, user_id)
    except Exception as e:
        logger.warning("Cannot get/create sandbox for terminal: %s", e)
        await websocket.close(code=4001)
        return
    sid = f"ws-pty-{uuid.uuid4().hex[:8]}"
    pty_handle = None
    loop = asyncio.get_running_loop()

    try:
        pty_handle = await asyncio.to_thread(
            sandbox.process.create_pty_session,
            id=sid,
            cwd="/home/daytona/workspace",
            envs={
                "TERM": "xterm-256color",
                # Use C.UTF-8 which is always available in any Linux container,
                # avoiding "setlocale: cannot change locale (en_US.UTF-8)" warnings.
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "LC_CTYPE": "C.UTF-8",
                "LC_COLLATE": "C.UTF-8",
            },
            pty_size=PtySize(cols=220, rows=50),
        )
    except Exception as e:
        logger.error("PTY create failed: %s", e)
        await websocket.close(code=4002)
        return

    try:
        output_queue: asyncio.Queue = asyncio.Queue(maxsize=_PTY_OUTPUT_QUEUE_MAX)

        def _enqueue_output(data) -> None:
            # Bound memory for slow clients: drop oldest output when queue is full.
            if output_queue.full():
                try:
                    output_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                output_queue.put_nowait(data)
            except asyncio.QueueFull:
                pass

        def _read_pty():
            try:
                for data in pty_handle:
                    loop.call_soon_threadsafe(_enqueue_output, data)
            except Exception:
                pass
            finally:
                loop.call_soon_threadsafe(_enqueue_output, None)

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
                            if raw.strip().startswith("{"):
                                try:
                                    pkt = json.loads(raw)
                                    pkt_type = pkt.get("type")
                                    if pkt_type == "resize":
                                        cols = int(pkt.get("cols", 80))
                                        rows = int(pkt.get("rows", 24))
                                        pty_handle.resize(PtySize(cols=cols, rows=rows))
                                        continue
                                    if pkt_type == "ctrl+c" or (
                                        pkt_type == "key"
                                        and pkt.get("ctrl") is True
                                        and pkt.get("key", "").lower() == "c"
                                    ):
                                        pty_handle.send_input("\x03")  # SIGINT
                                        continue
                                except Exception:
                                    pass
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
        if pty_handle:
            try:
                pty_handle.kill()
            except Exception:
                pass
