# pyright: basic
# type: ignore

"""
FilesystemService — file operations via Daytona SDK only.

Paths follow https://www.daytona.io/docs/en/file-system-operations/:
- "workspace" = sandbox working dir (/home/[username]/workspace)
- "workspace/relpath" for subpaths. No custom file list; use list_files / get_file_info only.
"""

import asyncio
import logging
from typing import Any, Optional

from workspace_manager import WorkspaceManager

logger = logging.getLogger("daytona-api")


def _workspace_path(relative_path: str = "") -> str:
    """Path for SDK: doc uses 'workspace' or 'workspace/...' (no leading slash)."""
    p = (relative_path or "").strip().strip("/")
    return f"workspace/{p}" if p else "workspace"


class FilesystemService:
    """File system operations via sandbox.fs (list_files, get_file_info, etc.)."""

    def __init__(self, workspace_manager: WorkspaceManager):
        self.wm = workspace_manager

    async def initialize(self, sandbox) -> bool:
        return await self.wm.initialize(sandbox)

    async def cleanup(self, sandbox) -> bool:
        return await self.wm.cleanup(sandbox)

    def get_path(self, relative_path: str = "") -> str:
        return self.wm.get_path(relative_path)

    async def list_files(self, path: str, sandbox) -> list[dict[str, Any]]:
        """List files/dirs via sandbox.fs.list_files (doc: List files and directories)."""
        try:
            await self.wm.initialize(sandbox)
            sdk_path = _workspace_path(path)
            files = sandbox.fs.list_files(sdk_path)
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
        """Build tree; runs blocking SDK calls in a thread to avoid blocking the event loop."""
        sdk_path = _workspace_path(path)
        rel_base = path or ""

        def build_tree(sdk_dir: str, rel_path: str, depth: int) -> Optional[dict[str, Any]]:
            if depth > max_depth:
                return None
            try:
                info = sandbox.fs.get_file_info(sdk_dir)
                node = {
                    "name": info.name,
                    "path": rel_path,
                    "type": "directory" if info.is_dir else "file",
                    "size": getattr(info, "size", 0),
                    "modified": getattr(info, "mod_time", ""),
                }
                if info.is_dir:
                    node["children"] = []
                    for f in sorted(sandbox.fs.list_files(sdk_dir), key=lambda x: (not x.is_dir, x.name)):
                        child_sdk = f"{sdk_dir}/{f.name}"
                        child_rel = f"{rel_path}/{f.name}".lstrip("/") if rel_path else f.name
                        child = build_tree(child_sdk, child_rel, depth + 1)
                        if child:
                            node["children"].append(child)
                return node
            except Exception as e:
                return {"name": sdk_dir.split("/")[-1], "error": str(e)}

        def _run():
            tree = build_tree(sdk_path, rel_base, 0)
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
            await self.wm.initialize(sandbox)
            content = sandbox.fs.download_file(_workspace_path(path)).decode("utf-8")
            return {"success": True, "content": content}
        except Exception as e:
            logger.error(f"read_file failed at {path}: {e}")
            return {"success": False, "error": str(e)}

    async def write_file(self, path: str, content: str, sandbox) -> bool:
        try:
            if not await self.wm.initialize(sandbox):
                return False
            sdk_path = _workspace_path(path)
            parts = path.strip("/").split("/")
            if len(parts) > 1:
                parent = "/".join(parts[:-1])
                try:
                    sandbox.fs.create_folder(_workspace_path(parent), "755")
                except Exception:
                    pass
            sandbox.fs.upload_file(content.encode("utf-8"), sdk_path)
            logger.info(f"File saved: {sdk_path}")
            return True
        except Exception as e:
            logger.error(f"write_file failed at {path}: {e}")
            return False

    async def create_file(self, path: str, sandbox, content: str = "") -> bool:
        try:
            if not await self.wm.initialize(sandbox):
                return False
            if not content:
                if path.endswith(".txt"):
                    content = "# Text file\n"
                elif path.endswith(".md"):
                    content = "# Markdown Document\n\nCreated by Daytona Editor\n"
            sdk_path = _workspace_path(path)
            parts = path.strip("/").split("/")
            if len(parts) > 1:
                parent = "/".join(parts[:-1])
                try:
                    sandbox.fs.create_folder(_workspace_path(parent), "755")
                except Exception:
                    pass
            sandbox.fs.upload_file(content.encode("utf-8"), sdk_path)
            logger.info(f"Created file: {sdk_path}")
            return True
        except Exception as e:
            logger.error(f"create_file failed at {path}: {e}")
            return False

    async def create_folder(self, path: str, sandbox, mode: str = "755") -> bool:
        try:
            if not await self.wm.initialize(sandbox):
                return False
            sandbox.fs.create_folder(_workspace_path(path), mode)
            logger.info(f"Created folder: {_workspace_path(path)}")
            return True
        except Exception as e:
            logger.error(f"create_folder failed at {path}: {e}")
            return False

    async def delete_path(self, path: str, sandbox) -> bool:
        try:
            sdk_path = _workspace_path(path)
            if not sdk_path.startswith("workspace"):
                logger.error(f"Security: delete outside workspace: {sdk_path}")
                return False
            sandbox.fs.delete_file(sdk_path, recursive=True)
            logger.info(f"Deleted: {sdk_path}")
            return True
        except Exception as e:
            logger.error(f"delete_path failed at {path}: {e}")
            return False

    async def search_files(self, pattern: str, sandbox, path: str = "") -> list[str]:
        try:
            sdk_path = _workspace_path(path)
            result = sandbox.fs.search_files(sdk_path, pattern)
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
            matches = sandbox.fs.find_files(sdk_path, pattern)
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
            sandbox.fs.move_files(sdk_src, sdk_dest)
            logger.info(f"Moved: {sdk_src} -> {sdk_dest}")
            return True
        except Exception as e:
            logger.error(f"move_files failed: {e}")
            return False

    async def get_file_info(self, path: str, sandbox) -> dict[str, Any]:
        try:
            info = sandbox.fs.get_file_info(_workspace_path(path))
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
            sandbox.fs.set_file_permissions(_workspace_path(path), mode=mode, owner=owner, group=group)
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
            results = sandbox.fs.replace_in_files(sdk_files, pattern, new_value)
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
