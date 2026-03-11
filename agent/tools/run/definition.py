# pyright: basic
# type: ignore

"""
RunFileTool — Run an existing file via POST /run API.
Mimics the "Run" button click in the UI.
"""

import logging
from collections.abc import Sequence
from typing import Any

import httpx
from pydantic import Field

from openhands.sdk import Action, Observation, TextContent, ImageContent, ToolDefinition
from openhands.sdk.tool import ToolExecutor

from pathlib import Path

from daytona import Sandbox

from config import settings

logger = logging.getLogger("agent-api")

_DESCRIPTION = """
Run an existing file by calling the sandbox /run API — exactly like clicking the "Run" button in the UI.

**When to use this tool:**
* User asks you to "run file X", "chạy file X", "execute file X"
* You need to run an existing file that is already saved in the sandbox workspace
* You want the output to appear the same way as if the user clicked the Run button

**This tool does NOT write code. It only runs existing files.**

**Parameters:**
* file_path (required): Relative path to the file inside workspace (e.g. "minh.py", "src/app.py")
* timeout: Maximum execution time in seconds (default: 60)
* use_jupyter: Use Jupyter kernel for rich output like charts/images (default: true)

**Examples:**
```
file_path="minh.py"
file_path="src/main.py", timeout=120
file_path="charts/plot.py", use_jupyter=true
```

**Output:** Returns the same output as the Run button — stdout, exit_code, and rich outputs (charts, images, HTML).

"""

class RunFileAction(Action):
    file_path: str = Field(description="Path to file in workspace (e.g. 'minh.py', 'src/app.py')")
    timeout: int = Field(default=60, description="Execution timeout in seconds")
    use_jupyter: bool = Field(default=True, description="Always True, kept for compatibility")
    working_dir: str = Field(default="", description="Ignored, kept for compatibility")


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

    def __call__(self, action: RunFileAction, conversation=None) -> RunFileObservation:
        try:
            file_path = action.file_path.strip()
            # Strip absolute workspace prefix if agent sends full path
            for prefix in ("/home/daytona/workspace/", "/home/daytona/workspace"):
                if file_path.startswith(prefix):
                    file_path = file_path[len(prefix):]
                    break
            file_path = file_path.lstrip("/")
            sdk_path = f"workspace/{file_path}" if not file_path.startswith("workspace") else file_path

            content_bytes = self.sandbox.fs.download_file(sdk_path)
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
