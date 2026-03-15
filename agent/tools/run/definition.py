# pyright: basic
# type: ignore

"""
RunFileTool — Run an existing file via POST /run API.
Mimics the "Run" button click in the UI.
"""

import logging
import posixpath
from collections.abc import Sequence
from typing import Any

import httpx
from pydantic import Field

from openhands.sdk import Action, Observation, TextContent, ImageContent, ToolDefinition
from openhands.sdk.tool import ToolExecutor

from daytona import Sandbox

from config import settings
from dependencies import WORKSPACE

logger = logging.getLogger("agent-api")

_DESCRIPTION = """
Run an existing file by calling the sandbox /run API — exactly like clicking the "Run" button in the UI.

**When to use this tool:**
* User asks you to "run file X", "chạy file X", "execute file X"
* You need to run an existing file that is already saved in the sandbox workspace
* You want the output to appear the same way as if the user clicked the Run button

**This tool does NOT write code. It only runs existing files.**

**Parameters:**
* file_path (required): Path to the file inside workspace (e.g. "minh.py", "src/app.py", "/home/daytona/workspace/src/app.py")
* timeout: Maximum execution time in seconds (default: 60)
* use_jupyter: Use Jupyter kernel for rich output like charts/images (default: true)
* working_dir: Optional workspace directory used to resolve relative file paths (e.g. "src", "/home/daytona/workspace/src")

**Examples:**
```
file_path="minh.py"
file_path="src/main.py", timeout=60
file_path="charts/plot.py", use_jupyter=true
```

**Output:** Returns the same output as the Run button — stdout, exit_code, and rich outputs (charts, images, HTML).

"""

class RunFileAction(Action):
    file_path: str = Field(
        description=(
            "Path to file in workspace. Supports workspace-relative paths like "
            "'main.py' or 'src/app.py', and absolute workspace paths like "
            "'/home/daytona/workspace/src/app.py'."
        )
    )
    timeout: int = Field(default=60, description="Execution timeout in seconds")
    use_jupyter: bool = Field(default=True, description="Always True, kept for compatibility")
    working_dir: str = Field(
        default="",
        description=(
            "Optional workspace directory used to resolve a relative file_path. "
            "Supports values like 'src' or '/home/daytona/workspace/src'."
        ),
    )


class RunFileObservation(Observation):
    output: str = ""
    exit_code: int = 0
    outputs: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        status = "SUCCESS" if self.exit_code == 0 else "ERROR"
        text = f"[Run button] {status} (exit code: {self.exit_code})\n\nOutput:\n{self.output}"
        if self.outputs:
            text += f"\n\n[Rich outputs: {len(self.outputs)} item(s)]"
        return [TextContent(text=text)]


class RunFileExecutor(ToolExecutor[RunFileAction, RunFileObservation]):
    def __init__(self, sandbox: Sandbox, execution_log: list | None = None):
        self.sandbox = sandbox
        self.execution_log: list[dict] = execution_log if execution_log is not None else []
        self.sandbox_api_url = settings.SANDBOX_API_URL.rstrip("/")

    def _strip_workspace_prefix(self, path: str) -> tuple[str, bool]:
        value = path.strip()
        if not value:
            return "", False

        workspace_prefixes = (
            f"{WORKSPACE}/",
            WORKSPACE,
            "/home/daytona/workspace/",
            "/home/daytona/workspace",
            "workspace/",
            "workspace",
        )
        for prefix in workspace_prefixes:
            if value == prefix:
                return "", True
            if value.startswith(f"{prefix}/"):
                return value[len(prefix) + 1 :], True
            if value.startswith(prefix) and prefix.endswith("/"):
                return value[len(prefix) :], True

        return value, False

    def _resolve_workspace_path(self, file_path: str, working_dir: str) -> str:
        raw_file_path = file_path.strip()
        if not raw_file_path:
            raise ValueError("file_path is required")

        file_rel_path, file_is_workspace_anchored = self._strip_workspace_prefix(raw_file_path)
        workdir_rel_path, _ = self._strip_workspace_prefix(working_dir or "")

        if file_rel_path.startswith("/"):
            raise ValueError(f"file_path must be inside {WORKSPACE}: {raw_file_path}")
        if workdir_rel_path.startswith("/"):
            raise ValueError(f"working_dir must be inside {WORKSPACE}: {working_dir}")

        resolved_path = file_rel_path
        if workdir_rel_path and not file_is_workspace_anchored:
            if resolved_path and not (
                resolved_path == workdir_rel_path or resolved_path.startswith(f"{workdir_rel_path}/")
            ):
                resolved_path = posixpath.join(workdir_rel_path, resolved_path)

        normalized_path = posixpath.normpath(resolved_path).lstrip("/")
        if normalized_path in ("", "."):
            raise ValueError("file_path must point to a file inside the workspace")
        if normalized_path == ".." or normalized_path.startswith("../"):
            raise ValueError(f"file_path escapes the workspace: {raw_file_path}")

        return normalized_path

    def __call__(self, action: RunFileAction, conversation=None) -> RunFileObservation:
        try:
            file_path = self._resolve_workspace_path(action.file_path, action.working_dir)
            sdk_path = f"workspace/{file_path}"

            try:
                content_bytes = self.sandbox.fs.download_file(sdk_path)
            except Exception as exc:
                raise FileNotFoundError(
                    "Failed to locate file in workspace: "
                    f"{file_path} (from file_path={action.file_path!r}, working_dir={action.working_dir!r})"
                ) from exc
            code = (
                content_bytes.decode("utf-8", errors="replace")
                if isinstance(content_bytes, bytes)
                else str(content_bytes)
            )

            resp = httpx.post(
                f"{self.sandbox_api_url}/run",
                json={
                    "code": code,
                    "use_jupyter": True,
                    "file_path": file_path,
                    "timeout": action.timeout,
                },
                timeout=action.timeout + 30,
            )
            resp.raise_for_status()
            result = resp.json()

            output = result.get("output", "")
            exit_code = result.get("exit_code", 0)
            success = result.get("success", exit_code == 0)
            outputs = result.get("outputs", [])

            self.execution_log.append({
                "file_path": file_path,
                "output": output,
                "exit_code": exit_code,
                "success": success,
                "outputs": outputs,
            })

            return RunFileObservation(
                output=output, exit_code=exit_code, outputs=outputs,
            )
        except Exception as e:
            logger.exception("RunFile error")
            self.execution_log.append({
                "file_path": action.file_path,
                "output": str(e),
                "exit_code": 1,
                "success": False,
                "outputs": [],
            })
            return RunFileObservation(output=str(e), exit_code=1)


class RunFileTool(ToolDefinition[RunFileAction, RunFileObservation]):
    """Run existing file via /run API (same as Run button)."""
    name = "daytona_run_file"

    @classmethod
    def create(cls, conv_state, *, sandbox: Sandbox, execution_log: list | None = None) -> Sequence[ToolDefinition]:
        executor = RunFileExecutor(sandbox, execution_log=execution_log)
        return [cls(
            description=_DESCRIPTION,
            action_type=RunFileAction,
            observation_type=RunFileObservation,
            executor=executor,
        )]
