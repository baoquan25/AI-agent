# pyright: basic
# type: ignore

"""Daytona terminal tool — Action, Observation, and ToolDefinition schemas."""

from collections.abc import Sequence
from typing import Optional

from pydantic import Field

from openhands.sdk import Action, Observation, TextContent, ImageContent, ToolDefinition
from openhands.sdk.tool import ToolExecutor

from daytona import Sandbox

from tools.terminal.constants import (
    DEFAULT_CWD,
    DEFAULT_TIMEOUT,
    TIMEOUT_MESSAGE,
)


# ── Action ────────────────────────────────────────────────────────────────────


class DaytonaTerminalAction(Action):
    """Schema for bash command execution in the Daytona sandbox."""

    command: str = Field(
        default="",
        description=(
            "The bash command to execute. Can be empty string to view additional "
            "logs when previous exit code is `-1`. Can be `C-c` (Ctrl+C) to "
            "interrupt the currently running process. Note: You can only execute "
            "one bash command at a time. If you need to run multiple commands "
            "sequentially, you can use `&&` or `;` to chain them together."
        ),
    )
    is_input: bool = Field(
        default=False,
        description=(
            "If True, the command is an input to the running process. "
            "If False, the command is a bash command to be executed in the terminal. "
            "Default is False."
        ),
    )
    timeout: int = Field(
        default=DEFAULT_TIMEOUT,
        ge=1,
        description=(
            f"Maximum execution time in seconds (default: {DEFAULT_TIMEOUT}). "
            "Use a higher value for long-running commands like installation or tests."
        ),
    )
    reset: bool = Field(
        default=False,
        description=(
            "If True, reset the terminal by clearing tracked state (working directory, "
            "env vars). Use this only when the terminal state seems corrupted. "
            "Note that all previously set environment variables and session state will "
            "be lost after reset. Cannot be used with is_input=True."
        ),
    )
    working_dir: Optional[str] = Field(
        default=None,
        description=(
            "Override working directory for this command. "
            "If not set, uses the last working directory "
            f"(initially {DEFAULT_CWD})."
        ),
    )


# ── Observation ───────────────────────────────────────────────────────────────


class DaytonaTerminalObservation(Observation):
    """Result from a terminal command execution in the Daytona sandbox."""

    command: str = ""
    output: str = ""
    exit_code: int = 0
    working_dir: str = DEFAULT_CWD
    truncated: bool = False
    timed_out: bool = False

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        parts: list[str] = []

        if self.is_error:
            parts.append(self.ERROR_MESSAGE_HEADER)

        if self.output:
            parts.append(self.output)

        parts.append(f"[Current working directory: {self.working_dir}]")

        if self.timed_out:
            parts.append(f"[Command timed out. {TIMEOUT_MESSAGE}]")
        else:
            parts.append(f"[Command finished with exit code {self.exit_code}]")

        if self.truncated:
            parts.append("[Output was truncated]")

        return [TextContent(text="\n".join(parts))]


# ── Tool description ──────────────────────────────────────────────────────────

TOOL_DESCRIPTION = """Execute a bash command in the terminal within a persistent shell session.


### Command Execution
* One command at a time: You can only execute one bash command at a time. If you need to run multiple commands sequentially, use `&&` or `;` to chain them together.
* Persistent session: Commands execute in a persistent shell session where environment variables, virtual environments, and working directory persist between commands.
* Shell options: Do NOT use `set -e`, `set -eu`, or `set -euo pipefail` in shell scripts or commands in this environment. The runtime may not support them and can cause unusable shell sessions. If you want to run multi-line bash commands, write the commands to a file and then run it, instead.

### Interacting with Running Processes
* If a previous command is still running (started with `&` or via background), you can use `is_input=true` to send text to its STDIN.
* Send special keys: `C-c` (Ctrl+C interrupt), `C-z` (suspend), `C-d` (EOF).

### Long-running Commands
* For commands that may run indefinitely, run them in the background and redirect output to a file, e.g. `python3 app.py > server.log 2>&1 &`.
* For commands that may run for a long time (e.g. installation or testing commands), or commands that run for a fixed amount of time (e.g. sleep), you should set the "timeout" parameter of your function call to an appropriate value.
* If a bash command returns exit code `-1`, this means the process timed out and is not yet finished. You may retry with a higher timeout.

### Best Practices
* Directory verification: Before creating new directories or files, first verify the parent directory exists and is the correct location.
* Directory management: Try to maintain working directory by using absolute paths and avoiding excessive use of `cd`.

### Output Handling
* Output truncation: If the output exceeds a maximum length, it will be truncated before being returned.

### Terminal Reset
* Terminal reset: If the terminal becomes unresponsive, you can set the "reset" parameter to `true` to reset all tracked state. This will clear working directory and environment variables.
* Warning: Resetting the terminal will lose all previously set environment variables, working directory changes, and any running processes. Use this only when the terminal stops responding to commands.
"""  # noqa: E501


# ── ToolDefinition ────────────────────────────────────────────────────────────


class DaytonaTerminalTool(ToolDefinition[DaytonaTerminalAction, DaytonaTerminalObservation]):
    """A ToolDefinition subclass that initializes a DaytonaTerminalExecutor."""

    name = "daytona_terminal"

    @classmethod
    def create(
        cls,
        conv_state,
        *,
        sandbox: Sandbox,
        executor: ToolExecutor | None = None,
    ) -> Sequence["DaytonaTerminalTool"]:
        """Initialize DaytonaTerminalTool with executor parameters.

        Args:
            conv_state: Conversation state (used by the SDK framework).
            sandbox: Daytona Sandbox instance for remote command execution.
            executor: Optional pre-built executor (for testing).
        """
        if executor is None:
            from tools.terminal.impl import DaytonaTerminalExecutor
            executor = DaytonaTerminalExecutor(sandbox=sandbox)

        return [
            cls(
                action_type=DaytonaTerminalAction,
                observation_type=DaytonaTerminalObservation,
                description=TOOL_DESCRIPTION,
                executor=executor,
            )
        ]
