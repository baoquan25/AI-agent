# pyright: basic
# type: ignore

"""
WorkspaceManager — ensures workspace path exists, resolves absolute paths.

Each sandbox is dedicated to one user, so no user_{id} sub-folders needed.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class WorkspaceManager:
    """Manages the workspace directory inside a Daytona sandbox."""

    def __init__(self, base_path: str = "/home/daytona/workspace"):
        self.base_path = base_path
        self._initialized = False

    def get_path(self, relative_path: str = "") -> str:
        """Resolve a relative path inside the workspace to an absolute path."""
        if relative_path:
            return f"{self.base_path}/{relative_path.lstrip('/')}"
        return self.base_path

    async def initialize(self, sandbox) -> bool:
        """Create the workspace directory if not already done."""
        if self._initialized:
            return True
        try:
            sandbox.fs.create_folder(self.base_path, "755")
            self._initialized = True
            logger.info(f"Workspace initialized: {self.base_path}")
            return True
        except Exception as e:
            error_msg = str(e) or "Empty error - sandbox fs API may be unreachable"
            logger.error(f"Failed to initialize workspace: [{type(e).__name__}] {error_msg}")
            try:
                logger.error(f"  Sandbox ID: {getattr(sandbox, 'id', 'unknown')}, State: {getattr(sandbox, 'state', 'unknown')}")
            except Exception:
                pass
            return False

    async def cleanup(self, sandbox) -> bool:
        """Delete the entire workspace."""
        try:
            sandbox.fs.delete_file(self.base_path, recursive=True)
            self._initialized = False
            logger.info(f"Workspace cleaned up: {self.base_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to cleanup workspace: {e}")
            return False

    def wrap_code(self, code: str, file_path: Optional[str] = None) -> str:
        """Wrap user code to execute inside the workspace context."""
        if file_path:
            file_dir = os.path.dirname(file_path)
            working_dir = f"{self.base_path}/{file_dir}" if file_dir else self.base_path
        else:
            working_dir = self.base_path

        return f"""
import os
import sys

WORKSPACE = '{self.base_path}'
WORKING_DIR = '{working_dir}'

os.makedirs(WORKING_DIR, exist_ok=True)
os.chdir(WORKING_DIR)

if WORKING_DIR not in sys.path:
    sys.path.insert(0, WORKING_DIR)
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

os.environ['HOME'] = WORKSPACE
os.environ['WORKSPACE'] = WORKSPACE
os.environ['PYTHONPATH'] = WORKING_DIR + ':' + WORKSPACE

{code}
"""
