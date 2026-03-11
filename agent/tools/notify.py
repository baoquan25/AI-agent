import json
import logging
from urllib import request, error

from config import settings
from dependencies import WORKSPACE

logger = logging.getLogger("agent-api")


def _strip_workspace(path: str) -> str:
    """Convert an absolute sandbox path to the relative path expected by /fs/notify."""
    prefix = WORKSPACE.rstrip("/") + "/"
    if path.startswith(prefix):
        return path[len(prefix):]
    if path == WORKSPACE or path == WORKSPACE.rstrip("/"):
        return ""
    return path.lstrip("/")


def notify_file_change(path: str, change: str = "updated") -> None:
    """POST to sandbox /fs/notify so file-tree WebSocket events reach the frontend.

    Args:
        path: Absolute path in the sandbox (e.g. /home/daytona/workspace/src/main.py).
        change: One of "added", "updated", "deleted".
    """
    rel = _strip_workspace(path)
    url = f"{settings.SANDBOX_API_URL.rstrip('/')}/fs/notify"
    payload = json.dumps({"path": rel, "change": change}).encode("utf-8")
    req = request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with request.urlopen(req, timeout=5) as resp:
            resp.read()
    except (error.HTTPError, error.URLError, OSError) as exc:
        logger.warning("notify_file_change failed for %s (%s): %s", rel, change, exc)
