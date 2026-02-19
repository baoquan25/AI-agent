# pyright: basic
# type: ignore

"""Pydantic models for Filesystem endpoints."""

from typing import Optional

from pydantic import BaseModel


class CreateFolderRequest(BaseModel):
    path: str
    mode: str = "755"


class CreateFileRequest(BaseModel):
    path: str
    content: str = ""


class WriteFileRequest(BaseModel):
    path: str
    content: str


class SearchRequest(BaseModel):
    pattern: str
    path: str = ""


class RenameRequest(BaseModel):
    source: str
    destination: str


class FindRequest(BaseModel):
    """Find text in file contents (find_files)."""
    path: str = ""
    pattern: str


class ReplaceRequest(BaseModel):
    """Replace text in files (replace_in_files)."""
    files: list[str]
    pattern: str
    new_value: str


class SetPermissionsRequest(BaseModel):
    """Set file permissions (set_file_permissions)."""
    path: str
    mode: Optional[str] = None
    owner: Optional[str] = None
    group: Optional[str] = None
