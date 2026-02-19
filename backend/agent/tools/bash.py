# pyright: basic
# type: ignore

"""
BashTool — Execute arbitrary bash commands in sandbox.

Cho phép agent chạy:
  - git (clone, commit, push, diff, log...)
  - npm / yarn / pip / cargo / go (quản lý package)
  - docker, curl, wget
  - ls, cp, mv, chmod, chown
  - Bất kỳ lệnh bash nào
"""

from collections.abc import Sequence
from typing import Optional

from pydantic import Field

from openhands.sdk import Action, Observation, TextContent, ImageContent, ToolDefinition
from openhands.sdk.tool import ToolExecutor

from pathlib import Path

from daytona import Sandbox

_DESCRIPTION = (Path(__file__).parent / "bash.txt").read_text(encoding="utf-8").strip()


# ── Action ──────────────────────────────────────────────────────────

class BashAction(Action):
    command: str = Field(
        description="Bash command to execute (e.g. 'git status', 'pip install requests', 'ls -la')"
    )
    working_dir: Optional[str] = Field(
        default=None,
        description="Optional: working directory to run the command in (absolute path)",
    )
    timeout: int = Field(
        default=60,
        description="Execution timeout in seconds (default: 60)",
    )


# ── Observation ─────────────────────────────────────────────────────

class BashObservation(Observation):
    output: str = ""
    exit_code: int = 0
    success: bool = True

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        status = "SUCCESS" if self.success else f"ERROR (exit code: {self.exit_code})"
        text = f"[{status}]\n{self.output}" if self.output else f"[{status}] (no output)"
        return [TextContent(text=text)]


# ── Executor ────────────────────────────────────────────────────────

class BashExecutor(ToolExecutor[BashAction, BashObservation]):
    """
    Executes bash commands via sandbox.process.exec.
    Supports working directory, timeout, and captures stdout+stderr.
    """

    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox

    def __call__(self, action: BashAction, conversation=None) -> BashObservation:
        try:
            cmd = action.command

            if action.working_dir:
                safe_dir = action.working_dir.replace("'", "'\\''")
                cmd = f"cd '{safe_dir}' && {cmd}"

            full_cmd = f"bash -c '{cmd.replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}' 2>&1"
            result = self.sandbox.process.exec(full_cmd, timeout=action.timeout)

            output = getattr(result, "result", "") or ""
            exit_code = getattr(result, "exit_code", 0) or 0

            max_chars = 50000
            if len(output) > max_chars:
                output = output[:max_chars] + f"\n\n... (output truncated at {max_chars} chars)"

            return BashObservation(
                output=output,
                exit_code=exit_code,
                success=(exit_code == 0),
            )
        except Exception as e:
            return BashObservation(
                output=str(e),
                exit_code=1,
                success=False,
            )


class BashTool(ToolDefinition[BashAction, BashObservation]):
    """Execute bash commands in sandbox."""
    name = "daytona_bash"

    @classmethod
    def create(cls, conv_state, *, sandbox: Sandbox) -> Sequence[ToolDefinition]:
        executor = BashExecutor(sandbox)
        return [cls(
            description=_DESCRIPTION,
            action_type=BashAction,
            observation_type=BashObservation,
            executor=executor,
        )]
