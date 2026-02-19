# pyright: basic
# type: ignore

import posixpath
from collections.abc import Sequence

from pydantic import Field

from openhands.sdk import Action, Observation, TextContent, ImageContent, ToolDefinition
from openhands.sdk.tool import ToolExecutor

from pathlib import Path

from daytona import Sandbox

_DESCRIPTION = (Path(__file__).parent / "code.txt").read_text(encoding="utf-8").strip()


# ── Action ──────────────────────────────────────────────────────────

class CodeAction(Action):
    """Action to execute code in Daytona sandbox."""
    code: str = Field(description="Code to execute (inline code or will be written to file_path first)")
    timeout: int = Field(default=30, description="Execution timeout in seconds")
    file_path: str = Field(default="", description="Optional: save code to this path in sandbox then run it")
    working_dir: str = Field(default="", description="Optional: cd to this directory before running code")


# ── Observation ─────────────────────────────────────────────────────

class CodeObservation(Observation):
    output: str = ""
    exit_code: int = 0
    success: bool = True

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        status = "SUCCESS" if self.success else "ERROR"
        text = f"{status} (exit code: {self.exit_code})\n\nOutput:\n{self.output}"
        return [TextContent(text=text)]


# ── Executor ────────────────────────────────────────────────────────

class CodeExecutor(ToolExecutor[CodeAction, CodeObservation]):
    def __init__(self, sandbox: Sandbox, execution_log: list | None = None):
        self.sandbox = sandbox
        self.execution_log: list[dict] = execution_log if execution_log is not None else []

    def __call__(self, action: CodeAction, conversation=None) -> CodeObservation:
        try:
            code_to_run = action.code

            if action.file_path:
                content_bytes = action.code.encode("utf-8")
                self.sandbox.fs.upload_file(content_bytes, action.file_path)

                file_dir = action.working_dir or posixpath.dirname(action.file_path)
                code_to_run = (
                    f"import os; os.chdir('{file_dir}')\n"
                    f"exec(open('{action.file_path}').read())"
                )
            elif action.working_dir:
                code_to_run = (
                    f"import os; os.chdir('{action.working_dir}')\n"
                    f"{action.code}"
                )

            result = self.sandbox.process.code_run(code_to_run, timeout=action.timeout)
            output = getattr(result, "result", "") or ""
            exit_code = getattr(result, "exit_code", 0) or 0

            msg = output
            if action.file_path:
                msg = f"[Saved to {action.file_path}]\n{output}"

            self.execution_log.append({
                "output": msg,
                "exit_code": exit_code,
                "success": exit_code == 0,
                "file_path": action.file_path or None,
            })

            return CodeObservation(output=msg, exit_code=exit_code, success=(exit_code == 0))
        except Exception as e:
            self.execution_log.append({
                "output": str(e),
                "exit_code": 1,
                "success": False,
                "file_path": action.file_path or None,
            })
            return CodeObservation(output=str(e), exit_code=1, success=False)


class CodeTool(ToolDefinition[CodeAction, CodeObservation]):
    """Execute code inside the sandbox."""
    name = "daytona_code_run"

    @classmethod
    def create(cls, conv_state, *, sandbox: Sandbox, execution_log: list | None = None) -> Sequence[ToolDefinition]:
        executor = CodeExecutor(sandbox, execution_log=execution_log)
        return [cls(
            description=_DESCRIPTION,
            action_type=CodeAction,
            observation_type=CodeObservation,
            executor=executor,
        )]
