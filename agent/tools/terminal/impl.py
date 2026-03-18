# pyright: basic
# type: ignore

"""Terminal executor — business logic for command execution."""

import logging
import re

from openhands.sdk.tool import ToolExecutor

from daytona import Sandbox

from tools.terminal.constants import (
    CWD_SENTINEL,
    DEFAULT_CWD,
    MAX_OUTPUT_CHARS,
    TIMEOUT_MESSAGE,
)
from tools.terminal.definition import (
    TerminalAction,
    TerminalObservation,
)

logger = logging.getLogger("agent-api")


class TerminalExecutor(ToolExecutor[TerminalAction, TerminalObservation]):
    """Executor for the terminal tool.

    Tracks working directory and environment variables across calls so that
    consecutive sandbox.process.exec() calls behave like a persistent session.
    """

    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox
        self._cwd: str = DEFAULT_CWD
        self._env_vars: dict[str, str] = {}

    # ── Public entry point ────────────────────────────────────────────────

    def __call__(
        self,
        action: TerminalAction,
        conversation=None,
    ) -> TerminalObservation:
        """Execute the terminal action."""
        # Validate: reset + is_input are mutually exclusive
        if action.reset and action.is_input:
            return TerminalObservation(
                command=action.command,
                output="Cannot use reset=true with is_input=true.",
                exit_code=1,
                working_dir=self._cwd,
                is_error=True,
            )

        # Handle reset
        if action.reset:
            reset_result = self._reset()
            if not action.command.strip():
                return reset_result
            action = TerminalAction(
                command=action.command,
                timeout=action.timeout,
                is_input=False,
                reset=False,
                working_dir=None,
            )

        # Handle is_input (send stdin / special keys)
        if action.is_input:
            return self._handle_is_input(action)

        # Handle normal command execution
        return self._execute_command(action)

    def close(self) -> None:
        """Clean up resources (no-op for sandbox executor)."""
        pass

    # ── Reset ─────────────────────────────────────────────────────────────

    def _reset(self) -> TerminalObservation:
        """Reset tracked state to defaults."""
        self._cwd = DEFAULT_CWD
        self._env_vars = {}
        logger.info("Terminal state reset: cwd and env vars cleared")
        return TerminalObservation(
            command="[RESET]",
            output=(
                "Terminal state has been reset. All previous environment "
                "variables and session state have been cleared."
            ),
            exit_code=0,
            working_dir=DEFAULT_CWD,
        )

    # ── is_input handling ─────────────────────────────────────────────────

    def _handle_is_input(self, action: TerminalAction) -> TerminalObservation:
        """Handle is_input: send stdin/signals to a running process."""
        command = action.command.strip()

        if _is_special_key(command):
            return self._send_special_key(command)

        return TerminalObservation(
            command=command,
            output=(
                "Sending stdin input to a running process is not supported in this "
                "sandbox mode. Each command runs as a separate process. "
                "To interact with a process, use a different approach:\n"
                "  - Run commands that complete on their own\n"
                "  - Use `echo 'input' | command` for piped input\n"
                "  - Use `C-c` (is_input=true) to send interrupt signal"
            ),
            exit_code=1,
            working_dir=self._cwd,
            is_error=True,
        )

    def _send_special_key(self, command: str) -> TerminalObservation:
        """Send a special key (C-c, C-z, C-d) as a signal."""
        signal_map = {
            "C-c": ("kill -INT $(pgrep -n -P 1) 2>/dev/null; echo 'Sent SIGINT'", "SIGINT (Ctrl+C)"),
            "C-z": ("kill -TSTP $(pgrep -n -P 1) 2>/dev/null; echo 'Sent SIGTSTP'", "SIGTSTP (Ctrl+Z)"),
            "C-d": ("echo 'EOF signal sent'", "EOF (Ctrl+D)"),
        }
        cmd, label = signal_map.get(command, (f"echo 'Unknown key: {command}'", command))
        try:
            result = self.sandbox.process.exec(cmd, timeout=10)
            raw_output = getattr(result, "result", "") or ""
            return TerminalObservation(
                command=command,
                output=f"[{label} sent to running process]\n{raw_output}".strip(),
                exit_code=0,
                working_dir=self._cwd,
            )
        except Exception as e:
            return TerminalObservation(
                command=command,
                output=f"Failed to send {label}: {e}",
                exit_code=1,
                working_dir=self._cwd,
                is_error=True,
            )

    # ── Normal command execution ──────────────────────────────────────────

    def _execute_command(self, action: TerminalAction) -> TerminalObservation:
        """Execute a normal bash command in the sandbox."""
        cwd = action.working_dir or self._cwd
        user_cmd = action.command.strip()

        if not user_cmd:
            return TerminalObservation(
                command="",
                output="No command provided.",
                exit_code=1,
                working_dir=cwd,
                is_error=True,
            )

        # Track export statements for env var persistence
        _track_exports(user_cmd, self._env_vars)

        # Build the wrapped command
        env_prefix = _build_env_prefix(self._env_vars)
        wrapped = (
            f"{env_prefix}"
            f"cd {_shell_quote(cwd)} 2>/dev/null\n"
            f"{user_cmd}\n"
            f"_ec=$?\necho\necho '{CWD_SENTINEL}'\"$(pwd)\"\nexit $_ec"
        )

        try:
            result = self.sandbox.process.exec(wrapped, timeout=action.timeout)

            raw_output = getattr(result, "result", "") or ""
            exit_code = getattr(result, "exit_code", 0) or 0

            output, new_cwd = _extract_cwd(raw_output, CWD_SENTINEL, cwd)

            truncated = False
            if len(output) > MAX_OUTPUT_CHARS:
                output = output[:MAX_OUTPUT_CHARS] + "\n... [output truncated]"
                truncated = True

            self._cwd = new_cwd

            return TerminalObservation(
                command=user_cmd,
                output=output,
                exit_code=exit_code,
                working_dir=new_cwd,
                truncated=truncated,
            )
        except TimeoutError:
            logger.warning(f"Command timed out after {action.timeout}s: {user_cmd[:100]}")
            return TerminalObservation(
                command=user_cmd,
                output=f"Command timed out after {action.timeout} seconds.\n{TIMEOUT_MESSAGE}",
                exit_code=-1,
                working_dir=cwd,
                timed_out=True,
            )
        except Exception as e:
            logger.exception("Terminal exec error")
            return TerminalObservation(
                command=user_cmd,
                output=str(e),
                exit_code=1,
                working_dir=cwd,
                is_error=True,
            )


# ── Utility functions ─────────────────────────────────────────────────────────


def _shell_quote(s: str) -> str:
    """Single-quote a string for safe shell interpolation."""
    return "'" + s.replace("'", "'\\''") + "'"


def _is_special_key(command: str) -> bool:
    """Check if command is a special key like C-c, C-z, C-d."""
    cmd = command.strip()
    return cmd.startswith("C-") and len(cmd) == 3


def _extract_cwd(raw: str, sentinel: str, fallback_cwd: str) -> tuple[str, str]:
    """Split raw output into (user_output, new_cwd)."""
    idx = raw.rfind(sentinel)
    if idx == -1:
        return raw.strip(), fallback_cwd

    user_output = raw[:idx].rstrip()
    cwd_part = raw[idx + len(sentinel):]
    new_cwd = cwd_part.strip().splitlines()[0].strip() if cwd_part.strip() else ""
    if not new_cwd or not new_cwd.startswith("/"):
        new_cwd = fallback_cwd

    return user_output, new_cwd


def _build_env_prefix(env_vars: dict[str, str]) -> str:
    """Build export statements for tracked env vars."""
    if not env_vars:
        return ""
    exports = [f"export {k}={_shell_quote(v)}" for k, v in env_vars.items()]
    return " && ".join(exports) + " && "


def _track_exports(command: str, env_vars: dict[str, str]) -> None:
    """Parse export statements from command and track them."""
    for match in re.finditer(r'export\s+(\w+)=([^\s;&|]+|"[^"]*"|\'[^\']*\')', command):
        key = match.group(1)
        value = match.group(2).strip("'\"")
        env_vars[key] = value
