# filesystem_service.py

from __future__ import annotations

import asyncio
import logging
import posixpath
import time
from typing import Any, Optional

from workspace_manager import WorkspaceManager

logger = logging.getLogger("daytona-api")

MAX_PATH_LEN = 4096    # bytes — Linux PATH_MAX
MAX_SEGMENT_LEN = 255  # bytes — Linux NAME_MAX


def normalize_path(path: str) -> str:

    path = path.strip().strip("/")

    if "\x00" in path:
        raise ValueError(f"Invalid characters in path: {path!r}")

    if not path:
        return ""

    normalized = posixpath.normpath(path.replace("\\", "/"))

    if normalized in (".", "..") or normalized.startswith("..") or normalized.startswith("/"):
        raise ValueError(f"Invalid path: {path!r}")

    parts = normalized.split("/")
    if ".." in parts:
        raise ValueError(f"Path traversal not allowed: {path!r}")

    if len(normalized.encode()) > MAX_PATH_LEN:
        raise ValueError(f"Path too long (max {MAX_PATH_LEN} bytes): {normalized[:80]!r}…")
    for segment in parts:
        if len(segment.encode()) > MAX_SEGMENT_LEN:
            raise ValueError(
                f"Path segment too long (max {MAX_SEGMENT_LEN} bytes): {segment[:40]!r}…"
            )

    return normalized



def _workspace_path(relative_path: str = "") -> str:
    p = (relative_path or "").strip().strip("/")
    return f"workspace/{p}" if p else "workspace"


def _is_binary_blob(raw: bytes) -> bool:
    """Heuristic: null byte or many non-text bytes in a sample → treat as binary."""
    if b"\x00" in raw:
        return True
    sample = raw[:8192] if len(raw) > 8192 else raw
    if not sample:
        return False
    # Count bytes that are not printable ASCII or common whitespace/newline.
    non_text = sum(1 for b in sample if b < 0x20 and b not in (0x09, 0x0A, 0x0D))
    if non_text > len(sample) * 0.05:
        return True
    return False


def _decode_text(raw: bytes) -> tuple[str, str]:
    """Decode bytes as text; use errors='replace' so we never raise on bad input."""
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace"), "utf-8 (replaced)"


class FilesystemService:
    def __init__(self, workspace_manager: WorkspaceManager):
        self.wm = workspace_manager
        # Fix 5.2: protect _created_dirs with an asyncio lock so concurrent
        # requests for the same sandbox don't race on the per-sandbox set.
        self._created_dirs: dict[str, set[str]] = {}
        self._dirs_lock = asyncio.Lock()

    async def initialize(self, sandbox) -> bool:
        return await self.wm.initialize(sandbox)

    async def cleanup(self, sandbox) -> bool:
        return await self.wm.cleanup(sandbox)

    def get_path(self, relative_path: str = "") -> str:
        return self.wm.get_path(relative_path)

    async def list_files(self, path: str, sandbox) -> list[dict[str, Any]]:
        """List files/dirs via sandbox.fs.list_files (doc: List files and directories)."""
        try:
            t0 = time.monotonic()
            sdk_path = _workspace_path(path)
            files = await asyncio.to_thread(sandbox.fs.list_files, sdk_path)
            t1 = time.monotonic()
            logger.info(
                "list_files(%s) sdk=%.0fms",
                path, (t1-t0)*1000,
            )
            return [
                {
                    "name": f.name,
                    "path": f"{path}/{f.name}".lstrip("/") if path else f.name,
                    "type": "directory" if f.is_dir else "file",
                    "size": getattr(f, "size", 0),
                    "modified": getattr(f, "mod_time", ""),
                    "permissions": getattr(f, "permissions", None) or getattr(f, "mode", ""),
                }
                for f in files
            ]
        except Exception as e:
            logger.error(f"list_files failed at {path}: {e}")
            return []

    async def get_tree(self, path: str, sandbox, max_depth: int = 4) -> dict[str, Any]:
        """Build tree using list_files only — avoids redundant get_file_info per node."""
        await self.wm.initialize(sandbox)
        sdk_path = _workspace_path(path)
        rel_base = path or ""

        def build_tree(sdk_dir: str, rel_path: str, depth: int) -> Optional[dict[str, Any]]:
            if depth > max_depth:
                return None
            try:
                children_raw = sorted(
                    sandbox.fs.list_files(sdk_dir),
                    key=lambda x: (not x.is_dir, x.name),
                )
                node = {
                    "name": sdk_dir.rsplit("/", 1)[-1],
                    "path": rel_path,
                    "type": "directory",
                    "children": [],
                }
                for f in children_raw:
                    child_rel = f"{rel_path}/{f.name}".lstrip("/") if rel_path else f.name
                    if f.is_dir:
                        child_sdk = f"{sdk_dir}/{f.name}"
                        child = build_tree(child_sdk, child_rel, depth + 1)
                        if child:
                            node["children"].append(child)
                    else:
                        node["children"].append({
                            "name": f.name,
                            "path": child_rel,
                            "type": "file",
                            "size": getattr(f, "size", 0),
                            "modified": getattr(f, "mod_time", ""),
                        })
                return node
            except Exception as e:
                return {"name": sdk_dir.split("/")[-1], "error": str(e)}

        def _run():
            t0 = time.monotonic()
            tree = build_tree(sdk_path, rel_base, 0)
            logger.info("get_tree(%s) total=%.0fms", path, (time.monotonic()-t0)*1000)
            if tree:
                tree["base_path"] = path or "/"
            return tree or {"error": "Failed to build tree"}

        try:
            return await asyncio.to_thread(_run)
        except Exception as e:
            logger.error(f"get_tree failed at {path}: {e}")
            return {"error": str(e)}

    async def read_file(self, path: str, sandbox) -> dict[str, Any]:
        try:
            if not path or not path.strip("/"):
                return {"success": False, "error": "read_file: path must not be empty"}
            t0 = time.monotonic()
            raw = await asyncio.to_thread(sandbox.fs.download_file, _workspace_path(path))
            t1 = time.monotonic()
            logger.info(
                "read_file(%s) sdk=%.0fms",
                path, (t1-t0)*1000,
            )

            # Avoid decoding binary or non-UTF-8 as UTF-8 (crashes / mojibake).
            is_binary = _is_binary_blob(raw)
            if is_binary:
                return {
                    "success": True,
                    "content": "",
                    "is_binary": True,
                    "encoding": "binary",
                }
            content, encoding = _decode_text(raw)
            return {
                "success": True,
                "content": content,
                "is_binary": False,
                "encoding": encoding,
            }
        except Exception as e:
            logger.error(f"read_file failed at {path}: {e}")
            return {"success": False, "error": str(e)}

    async def _reset_dir_cache(self, sandbox) -> None:
        sid = getattr(sandbox, "id", None)
        if sid:
            async with self._dirs_lock:
                self._created_dirs.pop(sid, None)

    async def _dirs_for(self, sandbox) -> set[str]:
        sid = getattr(sandbox, "id", None)
        if not sid:
            return set()
        async with self._dirs_lock:
            if sid not in self._created_dirs:
                self._created_dirs[sid] = set()
            return self._created_dirs[sid]

    async def _create_dir_if_needed(self, dir_path: str, sandbox) -> None:
        async with self._dirs_lock:
            sid = getattr(sandbox, "id", None)
            if sid:
                dirs = self._created_dirs.setdefault(sid, set())
                if dir_path in dirs:
                    return
        t0 = time.monotonic()
        try:
            await asyncio.to_thread(sandbox.fs.create_folder, _workspace_path(dir_path), "755")
        except Exception:
            pass  # already exists → treat as success
        logger.info("_create_dir(%s) sdk=%.0fms", dir_path, (time.monotonic()-t0)*1000)
        async with self._dirs_lock:
            sid = getattr(sandbox, "id", None)
            if sid:
                self._created_dirs.setdefault(sid, set()).add(dir_path)

    async def _ensure_workspace_and_parents(self, path: str, sandbox) -> bool:
        if not await self.wm.initialize(sandbox):
            return False
        parts = path.strip("/").split("/")
        dir_parts = parts[:-1]
        if not dir_parts:
            return True

        deepest = "/".join(dir_parts)

        # Fast path: deepest parent already cached → nothing to do.
        sid = getattr(sandbox, "id", None)
        if sid:
            async with self._dirs_lock:
                known = self._created_dirs.get(sid, set())
                if deepest in known:
                    return True

        # SDK create_folder uses MkdirAll — one call creates the full chain.
        await self._create_dir_if_needed(deepest, sandbox)

        # Cache all intermediate levels so future sibling files skip SDK calls.
        if sid:
            async with self._dirs_lock:
                dirs = self._created_dirs.setdefault(sid, set())
                for i in range(1, len(dir_parts) + 1):
                    dirs.add("/".join(dir_parts[:i]))
        return True

    async def write_file(self, path: str, content: str, sandbox) -> bool:
        try:
            if not path or not path.strip("/"):
                logger.error("write_file: path must not be empty (cannot write to workspace root directory)")
                return False
            t0 = time.monotonic()
            if not await self._ensure_workspace_and_parents(path, sandbox):
                return False
            t1 = time.monotonic()
            sdk_path = _workspace_path(path)
            data = content.encode("utf-8")
            await asyncio.to_thread(sandbox.fs.upload_file, data, sdk_path)
            t2 = time.monotonic()
            logger.info(
                "write_file(%s) parents=%.0fms upload=%.0fms total=%.0fms",
                path, (t1-t0)*1000, (t2-t1)*1000, (t2-t0)*1000,
            )
            return True
        except Exception as e:
            logger.error(f"write_file failed at {path}: {e}")
            return False

    async def create_file(self, path: str, sandbox, content: str = "") -> bool:
        try:
            if not path or not path.strip("/"):
                logger.error("create_file: path must not be empty (cannot create file at workspace root directory)")
                return False
            if not await self._ensure_workspace_and_parents(path, sandbox):
                return False
            if not content:
                if path.endswith(".txt"):
                    content = "# Text file\n"
                elif path.endswith(".md"):
                    content = "# Markdown Document\n\nCreated by Daytona Editor\n"
            sdk_path = _workspace_path(path)
            data = content.encode("utf-8")
            await asyncio.to_thread(sandbox.fs.upload_file, data, sdk_path)
            return True
        except Exception as e:
            logger.error(f"create_file failed at {path}: {e}")
            return False

    async def create_folder(self, path: str, sandbox, mode: str = "755") -> bool:
        try:
            if not await self.wm.initialize(sandbox):
                return False
            await asyncio.to_thread(sandbox.fs.create_folder, _workspace_path(path), mode)
            return True
        except Exception as e:
            logger.error(f"create_folder failed at {path}: {e}")
            return False

    async def delete_path(self, path: str, sandbox) -> bool:
        try:
            if not path or not path.strip("/"):
                logger.error("Security: refusing to delete workspace root")
                return False
            sdk_path = _workspace_path(path)
            if not sdk_path.startswith("workspace/") or sdk_path == "workspace":
                logger.error(f"Security: delete outside workspace: {sdk_path}")
                return False
            await asyncio.to_thread(sandbox.fs.delete_file, sdk_path, recursive=True)
            self.wm.invalidate(sandbox)
            await self._reset_dir_cache(sandbox)
            return True
        except Exception as e:
            logger.error(f"delete_path failed at {path}: {e}")
            return False

    async def search_files(self, pattern: str, sandbox, path: str = "") -> list[str]:
        try:
            sdk_path = _workspace_path(path)
            result = await asyncio.to_thread(sandbox.fs.search_files, sdk_path, pattern)
            files = result.files if hasattr(result, "files") else []
            out = []
            for f in files:
                if isinstance(f, str) and f.startswith("workspace/"):
                    out.append(f[len("workspace/"):].lstrip("/"))
                else:
                    out.append(f)
            return out
        except Exception as e:
            logger.error(f"search_files failed: {e}")
            return []

    async def find_in_files(self, path: str, pattern: str, sandbox) -> list[dict[str, Any]]:
        try:
            sdk_path = _workspace_path(path)
            matches = await asyncio.to_thread(sandbox.fs.find_files, sdk_path, pattern)
            result = []
            for match in matches:
                file_path = getattr(match, "file", "")
                if file_path.startswith("workspace/"):
                    file_path = file_path[len("workspace/"):].lstrip("/")
                result.append({
                    "file": file_path,
                    "line": getattr(match, "line", 0),
                    "content": getattr(match, "content", ""),
                })
            return result
        except Exception as e:
            logger.error(f"find_in_files failed: {e}")
            return []

    async def move_files(self, source: str, destination: str, sandbox) -> bool:
        try:
            sdk_src = _workspace_path(source)
            sdk_dest = _workspace_path(destination)
            if not sdk_src.startswith("workspace") or not sdk_dest.startswith("workspace"):
                logger.error("Security: move outside workspace")
                return False
            await asyncio.to_thread(sandbox.fs.move_files, sdk_src, sdk_dest)
            self.wm.invalidate(sandbox)
            await self._reset_dir_cache(sandbox)
            return True
        except Exception as e:
            logger.error(f"move_files failed: {e}")
            return False

    async def get_file_info(self, path: str, sandbox) -> dict[str, Any]:
        try:
            t0 = time.monotonic()
            info = await asyncio.to_thread(sandbox.fs.get_file_info, _workspace_path(path))
            logger.info("get_file_info(%s) sdk=%.0fms", path, (time.monotonic()-t0)*1000)
            return {
                "name": info.name,
                "path": path,
                "type": "directory" if info.is_dir else "file",
                "size": getattr(info, "size", 0),
                "modified": getattr(info, "mod_time", ""),
                "permissions": getattr(info, "permissions", None) or getattr(info, "mode", ""),
                "owner": getattr(info, "owner", None),
                "group": getattr(info, "group", None),
            }
        except Exception as e:
            logger.error(f"get_file_info failed at {path}: {e}")
            return {"error": str(e)}

    async def set_file_permissions(self, path: str, sandbox,
                                   mode: Optional[str] = None,
                                   owner: Optional[str] = None,
                                   group: Optional[str] = None) -> bool:
        try:
            await asyncio.to_thread(
                sandbox.fs.set_file_permissions, _workspace_path(path),
                mode=mode, owner=owner, group=group
            )
            return True
        except Exception as e:
            logger.error(f"set_file_permissions failed at {path}: {e}")
            return False

    async def replace_in_files(
        self, files: list[str], pattern: str, new_value: str, sandbox
    ) -> list[dict[str, Any]]:
        """Replace text in files via sandbox.fs.replace_in_files (doc: replace_in_files)."""
        try:
            sdk_files = [_workspace_path(f) for f in files]
            results = await asyncio.to_thread(sandbox.fs.replace_in_files, sdk_files, pattern, new_value)
            out = []
            for r in results:
                file_path = getattr(r, "file", "")
                if file_path.startswith("workspace/"):
                    file_path = file_path[len("workspace/"):].lstrip("/")
                out.append({
                    "file": file_path,
                    "success": getattr(r, "success", False),
                    "error": getattr(r, "error", None),
                })
            return out
        except Exception as e:
            logger.error(f"replace_in_files failed: {e}")
            return []
