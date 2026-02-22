import os
import logging

logger = logging.getLogger(__name__)


class WorkspaceManager:
    """Manages the workspace directory inside a Daytona sandbox."""

    def __init__(self, base_path: str = "/home/daytona/workspace"):
        self.base_path = base_path
        # Track initialized per sandbox_id (not a single bool)
        self._initialized_sandboxes: set[str] = set()

    def get_path(self, relative_path: str = "") -> str:
        """Resolve a relative path inside the workspace to an absolute path."""
        if relative_path:
            return f"{self.base_path}/{relative_path.lstrip('/')}"
        return self.base_path

    def wrap_code(self, code: str, file_path: str) -> str:
        """Wrap code to run in the directory of file_path (for /run with file_path)."""
        if not file_path:
            return code
        dir_part = os.path.dirname(file_path)
        if not dir_part:
            return code
        abs_dir = f"{self.base_path}/{dir_part}".replace("//", "/")
        return f"import os\nos.chdir({repr(abs_dir)})\n{code}"

    async def initialize(self, sandbox) -> bool:
        """Create the workspace directory if not already done for this sandbox."""
        sandbox_id = getattr(sandbox, "id", None)
        if sandbox_id and sandbox_id in self._initialized_sandboxes:
            return True
        try:
            sandbox.fs.create_folder(self.base_path, "755")
            if sandbox_id:
                self._initialized_sandboxes.add(sandbox_id)
            logger.info(f"Workspace initialized: {self.base_path} (sandbox={sandbox_id})")
            return True
        except Exception as e:
            error_msg = str(e) or "Empty error - sandbox fs API may be unreachable"
            logger.error(f"Failed to initialize workspace: [{type(e).__name__}] {error_msg}")
            try:
                logger.error(f"  Sandbox ID: {sandbox_id}, State: {getattr(sandbox, 'state', 'unknown')}")
            except Exception:
                pass
            return False

    async def cleanup(self, sandbox) -> bool:
        """Delete the entire workspace using the same SDK method as FilesystemService."""
        sandbox_id = getattr(sandbox, "id", None)
        sdk_path = "workspace"  # SDK path (no leading slash), mirrors _workspace_path("")
        try:
            sandbox.fs.delete_file(sdk_path, recursive=True)
            self._initialized_sandboxes.discard(sandbox_id)
            logger.info(f"Workspace cleaned: {self.base_path} (sandbox={sandbox_id})")
            return True
        except Exception as e:
            logger.error(f"Workspace cleanup failed: {e}")
            return False
