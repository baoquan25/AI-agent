# pyright: basic
# type: ignore

import os
import time
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Depends, Response
from fastapi.responses import JSONResponse

from config import FILE_CACHE_MAX_SIZE, FILE_CACHE_TTL_SECONDS
from dependencies import get_sandbox, get_filesystem_service
from models.filesystem import (
    CreateFolderRequest,
    CreateFileRequest,
    WriteFileRequest,
    SearchRequest,
    RenameRequest,
    FindRequest,
    ReplaceRequest,
    SetPermissionsRequest,
)
from services.file_cache import (
    FileCache,
    generate_etag_from_metadata,
    get_cache_key,
    normalize_etag,
    clamp_ttl,
)

logger = logging.getLogger("daytona-api")

MAX_TREE_DEPTH = 4

# ── Global cache instance ───────────────────────────────────────────

_file_cache = FileCache(
    max_size=FILE_CACHE_MAX_SIZE,
    ttl_seconds=FILE_CACHE_TTL_SECONDS,
)
logger.info(
    f"File cache initialized: max_size={FILE_CACHE_MAX_SIZE}, "
    f"ttl={FILE_CACHE_TTL_SECONDS}s"
)


# ── Path validation ─────────────────────────────────────────────────

def _normalize_path(path: str) -> str:
    path = path.strip().strip("/")
    if "\x00" in path:
        raise ValueError(f"Invalid characters in path: {path}")
    # Empty string = workspace root → return "" directly, avoid normpath → "."
    if not path:
        return ""
    normalized = os.path.normpath(path)
    if normalized in (".", "..") or normalized.startswith("..") or normalized.startswith("/"):
        raise ValueError(f"Invalid path: {path}")
    parts = normalized.replace("\\", "/").split("/")
    if ".." in parts:
        raise ValueError(f"Path traversal not allowed: {path}")
    return normalized


def _validate_user_path(user_id: str, path: str) -> str:
    try:
        return _normalize_path(path)
    except ValueError as e:
        logger.warning(f"Invalid path for user {user_id}: {path}")
        raise HTTPException(status_code=400, detail=str(e))


def _invalidate_cache(user_id: str, path: str) -> None:
    cache_key = get_cache_key(user_id, path)
    _file_cache.invalidate(cache_key)


# ── Router ──────────────────────────────────────────────────────────

router = APIRouter(prefix="/fs", tags=["FileSystem"])


@router.get("/tree")
async def get_file_tree(
    path: str = "",
    max_depth: int = 4,
    user_id: str = Header(default="default_user", alias="X-User-ID"),
    sb_and_id=Depends(get_sandbox),
    fs=Depends(get_filesystem_service),
):
    sandbox, sid = sb_and_id
    safe_path = _validate_user_path(user_id, path) if path else ""
    depth = min(max_depth, MAX_TREE_DEPTH)
    try:
        tree = await fs.get_tree(safe_path, sandbox, depth)
        return {"success": True, "sandbox_id": sid, "user_id": user_id, "tree": tree}
    except Exception as e:
        logger.error(f"Failed to get file tree: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_files(
    path: str = "",
    user_id: str = Header(default="default_user", alias="X-User-ID"),
    sb_and_id=Depends(get_sandbox),
    fs=Depends(get_filesystem_service),
):
    sandbox, sid = sb_and_id
    safe_path = _validate_user_path(user_id, path) if path else ""
    try:
        files = await fs.list_files(safe_path, sandbox)
        return {
            "success": True, "sandbox_id": sid, "user_id": user_id,
            "path": safe_path, "files": files, "count": len(files),
        }
    except Exception as e:
        logger.error(f"Failed to list files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/file/content")
async def read_file_content(
    path: str,
    user_id: str = Header(default="default_user", alias="X-User-ID"),
    if_none_match: Optional[str] = Header(default=None, alias="If-None-Match"),
    sb_and_id=Depends(get_sandbox),
    fs=Depends(get_filesystem_service),
):
    sandbox, sid = sb_and_id
    safe_path = _validate_user_path(user_id, path)
    cache_key = get_cache_key(user_id, safe_path)
    normalized_etag = normalize_etag(if_none_match)

    try:
        file_info = await fs.get_file_info(safe_path, sandbox)
        if "error" in file_info:
            raise HTTPException(status_code=404, detail=file_info.get("error", "File not found"))

        current_modified = str(file_info.get("modified", ""))
        current_size = int(file_info.get("size", 0))
        current_etag = generate_etag_from_metadata(current_modified, current_size)

        cached = _file_cache.get(cache_key)

        if normalized_etag and normalized_etag == current_etag:
            ttl_remaining = _file_cache.ttl_seconds - (time.time() - cached.timestamp) if cached else 0
            return Response(
                status_code=304,
                headers={
                    "ETag": f'"{current_etag}"',
                    "X-Cache": "HIT",
                    "X-Cache-TTL": str(clamp_ttl(ttl_remaining)),
                },
            )

        result = await fs.read_file(safe_path, sandbox)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("error", "File not found"))

        content = result.get("content", "")
        _file_cache.set(cache_key, etag=current_etag, modified=current_modified)

        return JSONResponse(
            content={
                "success": True, "sandbox_id": sid, "user_id": user_id,
                "path": safe_path, "content": content,
                "etag": current_etag, "modified": current_modified, "size": current_size,
            },
            headers={
                "ETag": f'"{current_etag}"',
                "X-Cache": "MISS",
                "X-Cache-TTL": str(clamp_ttl(_file_cache.ttl_seconds)),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to read file for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/file/content")
async def write_file_content(
    request: WriteFileRequest,
    user_id: str = Header(default="default_user", alias="X-User-ID"),
    if_match: Optional[str] = Header(default=None, alias="If-Match"),
    sb_and_id=Depends(get_sandbox),
    fs=Depends(get_filesystem_service),
):
    sandbox, sid = sb_and_id
    safe_path = _validate_user_path(user_id, request.path)
    expected_etag = normalize_etag(if_match)

    try:
        if expected_etag:
            file_info = await fs.get_file_info(safe_path, sandbox)
            if "error" not in file_info:
                current_modified = str(file_info.get("modified", ""))
                current_size = int(file_info.get("size", 0))
                current_etag = generate_etag_from_metadata(current_modified, current_size)
                if current_etag != expected_etag:
                    logger.warning(
                        f"Conflict for user {user_id}, file {safe_path}: "
                        f"expected={expected_etag}, current={current_etag}"
                    )
                    return JSONResponse(
                        status_code=412,
                        content={
                            "success": False, "error": "Precondition Failed",
                            "message": "File was modified by another tab or user. Please refresh and try again.",
                            "expected_etag": expected_etag, "current_etag": current_etag,
                            "path": safe_path,
                        },
                        headers={"ETag": f'"{current_etag}"'},
                    )

        success = await fs.write_file(safe_path, request.content, sandbox)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save file")

        _invalidate_cache(user_id, safe_path)

        file_info = await fs.get_file_info(safe_path, sandbox)
        new_modified = str(file_info.get("modified", ""))
        new_size = int(file_info.get("size", len(request.content.encode("utf-8"))))
        new_etag = generate_etag_from_metadata(new_modified, new_size)

        cache_key = get_cache_key(user_id, safe_path)
        _file_cache.set(cache_key, etag=new_etag, modified=new_modified)

        return JSONResponse(
            content={
                "success": True, "sandbox_id": sid, "user_id": user_id,
                "path": safe_path, "message": f"File saved: {safe_path}",
                "etag": new_etag, "modified": new_modified, "size": new_size,
            },
            headers={"ETag": f'"{new_etag}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to write file for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/folder")
async def create_folder(
    request: CreateFolderRequest,
    user_id: str = Header(default="default_user", alias="X-User-ID"),
    sb_and_id=Depends(get_sandbox),
    fs=Depends(get_filesystem_service),
):
    sandbox, sid = sb_and_id
    safe_path = _validate_user_path(user_id, request.path)
    try:
        success = await fs.create_folder(safe_path, sandbox, mode=request.mode)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to create folder")
        return {
            "success": True, "sandbox_id": sid, "user_id": user_id,
            "path": safe_path, "message": f"Folder created: {safe_path}",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create folder for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/file")
async def create_file(
    request: CreateFileRequest,
    user_id: str = Header(default="default_user", alias="X-User-ID"),
    sb_and_id=Depends(get_sandbox),
    fs=Depends(get_filesystem_service),
):
    sandbox, sid = sb_and_id
    safe_path = _validate_user_path(user_id, request.path)
    try:
        success = await fs.create_file(safe_path, sandbox, request.content)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to create file")

        file_info = await fs.get_file_info(safe_path, sandbox)
        new_modified = str(file_info.get("modified", ""))
        new_size = int(file_info.get("size", len((request.content or "").encode("utf-8"))))
        new_etag = generate_etag_from_metadata(new_modified, new_size)

        cache_key = get_cache_key(user_id, safe_path)
        _file_cache.set(cache_key, etag=new_etag, modified=new_modified)

        return JSONResponse(
            content={
                "success": True, "sandbox_id": sid, "user_id": user_id,
                "path": safe_path, "message": f"File created: {safe_path}",
                "etag": new_etag, "modified": new_modified, "size": new_size,
            },
            headers={"ETag": f'"{new_etag}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create file for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/path")
async def delete_path(
    path: str,
    user_id: str = Header(default="default_user", alias="X-User-ID"),
    sb_and_id=Depends(get_sandbox),
    fs=Depends(get_filesystem_service),
):
    sandbox, sid = sb_and_id
    safe_path = _validate_user_path(user_id, path)
    if not safe_path:
        raise HTTPException(status_code=400, detail="Cannot delete workspace root")
    try:
        success = await fs.delete_path(safe_path, sandbox)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete path")
        _invalidate_cache(user_id, safe_path)
        prefix = get_cache_key(user_id, safe_path)
        _file_cache.invalidate_prefix(prefix)
        return {
            "success": True, "sandbox_id": sid, "user_id": user_id,
            "path": safe_path, "message": f"Path deleted: {safe_path}",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete path for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rename")
async def rename_path(
    request: RenameRequest,
    user_id: str = Header(default="default_user", alias="X-User-ID"),
    sb_and_id=Depends(get_sandbox),
    fs=Depends(get_filesystem_service),
):
    sandbox, sid = sb_and_id
    safe_source = _validate_user_path(user_id, request.source)
    safe_dest = _validate_user_path(user_id, request.destination)
    try:
        success = await fs.move_files(safe_source, safe_dest, sandbox)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to rename/move")
        
        # Invalidate cache for both source and destination
        _invalidate_cache(user_id, safe_source)
        _invalidate_cache(user_id, safe_dest)
        
        # If moving directory, invalidate all children
        source_prefix = get_cache_key(user_id, safe_source)
        _file_cache.invalidate_prefix(source_prefix)
        
        return {
            "success": True, "sandbox_id": sid, "user_id": user_id,
            "source": safe_source, "destination": safe_dest,
            "message": f"Renamed: {safe_source} → {safe_dest}",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to rename path for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/find")
async def find_in_files(
    request: FindRequest,
    user_id: str = Header(default="default_user", alias="X-User-ID"),
    sb_and_id=Depends(get_sandbox),
    fs=Depends(get_filesystem_service),
):
    """Find text in file contents (find_files). Searches recursively if path is a directory."""
    sandbox, sid = sb_and_id
    safe_path = _validate_user_path(user_id, request.path) if request.path else ""
    try:
        matches = await fs.find_in_files(safe_path, request.pattern, sandbox)
        return {
            "success": True,
            "sandbox_id": sid,
            "user_id": user_id,
            "path": safe_path,
            "pattern": request.pattern,
            "matches": matches,
            "count": len(matches),
        }
    except Exception as e:
        logger.error(f"Failed to find in files for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_files(
    request: SearchRequest,
    user_id: str = Header(default="default_user", alias="X-User-ID"),
    sb_and_id=Depends(get_sandbox),
    fs=Depends(get_filesystem_service),
):
    sandbox, sid = sb_and_id
    safe_path = _validate_user_path(user_id, request.path) if request.path else ""
    try:
        matches = await fs.search_files(request.pattern, sandbox, safe_path)
        return {
            "success": True, "sandbox_id": sid, "user_id": user_id,
            "pattern": request.pattern, "path": safe_path,
            "matches": matches, "count": len(matches),
        }
    except Exception as e:
        logger.error(f"Failed to search files for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/replace")
async def replace_in_files(
    request: ReplaceRequest,
    user_id: str = Header(default="default_user", alias="X-User-ID"),
    sb_and_id=Depends(get_sandbox),
    fs=Depends(get_filesystem_service),
):
    """Replace text in multiple files (replace_in_files)."""
    sandbox, sid = sb_and_id
    safe_files = [_validate_user_path(user_id, f) for f in request.files]
    try:
        results = await fs.replace_in_files(
            safe_files, request.pattern, request.new_value, sandbox
        )
        for path in safe_files:
            _invalidate_cache(user_id, path)
        return {
            "success": True,
            "sandbox_id": sid,
            "user_id": user_id,
            "results": results,
            "count": len(results),
        }
    except Exception as e:
        logger.error(f"Failed to replace in files for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/permissions")
async def set_file_permissions(
    request: SetPermissionsRequest,
    user_id: str = Header(default="default_user", alias="X-User-ID"),
    sb_and_id=Depends(get_sandbox),
    fs=Depends(get_filesystem_service),
):
    """Set file permissions and ownership (set_file_permissions)."""
    sandbox, sid = sb_and_id
    safe_path = _validate_user_path(user_id, request.path)
    try:
        success = await fs.set_file_permissions(
            safe_path,
            sandbox,
            mode=request.mode,
            owner=request.owner,
            group=request.group,
        )
        if not success:
            raise HTTPException(status_code=500, detail="Failed to set file permissions")
        return {
            "success": True,
            "sandbox_id": sid,
            "user_id": user_id,
            "path": safe_path,
            "message": f"Permissions updated: {safe_path}",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set permissions for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/init")
async def initialize_workspace(
    user_id: str = Header(default="default_user", alias="X-User-ID"),
    sb_and_id=Depends(get_sandbox),
    fs=Depends(get_filesystem_service),
):
    sandbox, sid = sb_and_id
    try:
        success = await fs.initialize(sandbox)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to initialize workspace")
        return {
            "success": True, "sandbox_id": sid, "user_id": user_id,
            "message": "Workspace initialized",
            "workspace_path": fs.get_path(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initialize workspace for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cleanup")
async def cleanup_workspace(
    user_id: str = Header(..., alias="X-User-ID"),
    sb_and_id=Depends(get_sandbox),
    fs=Depends(get_filesystem_service),
):
    sandbox, sid = sb_and_id
    try:
        success = await fs.cleanup(sandbox)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to cleanup workspace")
        cleared = _file_cache.invalidate_user(user_id)
        return {
            "success": True, "sandbox_id": sid, "user_id": user_id,
            "message": "Workspace cleaned up",
            "cache_entries_cleared": cleared,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cleanup workspace for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Cache Management Endpoints ──────────────────────────────────────

@router.get("/cache/stats", tags=["Cache"])
async def get_cache_stats():
    return {"success": True, "cache": _file_cache.get_stats()}


@router.post("/cache/cleanup", tags=["Cache"])
async def cleanup_expired_cache():
    removed = _file_cache.cleanup_expired()
    return {"success": True, "expired_entries_removed": removed, "cache": _file_cache.get_stats()}


@router.delete("/cache/clear", tags=["Cache"])
async def clear_all_cache():
    cleared = _file_cache.clear()
    return {"success": True, "entries_cleared": cleared, "cache": _file_cache.get_stats()}


@router.delete("/cache/user/{target_user_id}", tags=["Cache"])
async def clear_user_cache(target_user_id: str):
    cleared = _file_cache.invalidate_user(target_user_id)
    return {
        "success": True, "user_id": target_user_id,
        "entries_cleared": cleared, "cache": _file_cache.get_stats(),
    }
