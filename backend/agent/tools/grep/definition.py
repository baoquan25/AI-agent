# pyright: basic
# type: ignore

from collections.abc import Sequence
from typing import Optional

from pydantic import Field

from openhands.sdk import Action, Observation, TextContent, ImageContent, ToolDefinition
from openhands.sdk.tool import ToolAnnotations, ToolExecutor

from daytona import Sandbox
from dependencies import WORKSPACE

_DESCRIPTION = """
Search file contents in the sandbox using plain text or regular expressions.

This tool searches recursively under a given path and returns files or lines
that match the provided pattern.

Useful for:
- finding where a function, class, variable, or import is defined or used
- locating TODOs, error messages, or specific strings
- searching code with regular expressions
- identifying which files contain a match

Behavior:
- searches recursively from the provided path
- supports plain text and full regular expressions
- skips binary files automatically
- excludes common generated or hidden directories such as:
  .git, node_modules, __pycache__, .venv, .mypy_cache, .tox, dist, and build
- can filter searched files with a glob pattern such as "*.py"
- returns at most the first 100 results
- uses ripgrep when available, otherwise falls back to grep

Parameters:
- pattern: required; text or regex pattern to search for
- path: optional; root directory to search recursively
- include: optional; glob pattern to restrict searched files
- case_sensitive: optional; defaults to true
- context_lines: optional; number of surrounding lines to include, from 0 to 5
- files_only: optional; when true, returns only file paths that contain matches

Output:
- default mode: filepath:line_number:matching_line
- files_only=true: filepath
"""

class GrepAction(Action):
    pattern: str = Field(description="Regex or text pattern to search for inside files")
    path: str = Field(
        default=WORKSPACE,
        description="Absolute directory path to search in (searches recursively)",
    )
    include: Optional[str] = Field(
        default=None,
        description="Optional glob to filter files (e.g. '*.py', '*.{ts,tsx}')",
    )
    case_sensitive: bool = Field(
        default=True,
        description="Case sensitive search (default: true, set false for case-insensitive)",
    )
    context_lines: int = Field(
        default=0,
        description="Lines of context around each match, 0-5 (default: 0)",
        ge=0,
        le=5,
    )
    files_only: bool = Field(
        default=False,
        description="Return only file paths instead of matching lines (default: false)",
    )


class GrepObservation(Observation):
    matches: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    count: int = 0
    success: bool = True
    files_only: bool = Field(default=False, description="Whether this was a files-only search")

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        if not self.success:
            return [TextContent(text=f"FAILED: {self.matches[0] if self.matches else 'unknown error'}")]
        if self.count == 0:
            return [TextContent(text="No matches found.")]

        files_list = "\n".join(f"  - {f}" for f in self.files[:20])

        if self.files_only:
            more = "\n  ... (truncated)" if len(self.files) > 20 else ""
            return [TextContent(
                text=f"Found {len(self.files)} matching file(s).\n\n"
                     f"Files:\n{files_list}{more}"
            )]

        sample = "\n".join(self.matches[:30])
        more = "\n  ... (truncated)" if self.count > 30 else ""
        return [TextContent(
            text=f"Found {self.count} matching line(s) in {len(self.files)} file(s).\n\n"
                 f"Files:\n{files_list}\n\n"
                 f"Matches:\n{sample}{more}"
        )]

_EXCLUDE_DIRS = [".git", "node_modules", "__pycache__", ".venv", ".mypy_cache", ".tox", "dist", "build"]


class GrepExecutor(ToolExecutor[GrepAction, GrepObservation]):
    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox
        rg_check = self.sandbox.process.exec("which rg 2>/dev/null", timeout=5)
        self._has_ripgrep = bool(getattr(rg_check, "result", "").strip())

    def _build_ripgrep_cmd(self, action: GrepAction) -> str:
        safe_pattern = action.pattern.replace("'", "'\\''")
        safe_path = self._normalize_search_path(action.path).replace("'", "'\\''")

        cmd = "rg --no-heading -Hn"

        if not action.case_sensitive:
            cmd += " -i"

        if action.files_only:
            cmd += " -l"
        elif action.context_lines > 0:
            cmd += f" -C {action.context_lines}"

        if action.include:
            safe_include = action.include.replace("'", "'\\''")
            cmd += f" -g '{safe_include}'"

        for d in _EXCLUDE_DIRS:
            cmd += f" -g '!{d}/'"

        cmd += f" -e '{safe_pattern}' '{safe_path}' 2>/dev/null | head -100"
        return cmd

    def _build_grep_cmd(self, action: GrepAction) -> str:
        safe_pattern = action.pattern.replace("'", "'\\''")
        safe_path = self._normalize_search_path(action.path).replace("'", "'\\''")

        cmd = "grep -rHnEI"

        if not action.case_sensitive:
            cmd += " -i"

        if action.files_only:
            cmd = cmd.replace("-rHnEI", "-rlEI")  # -l for files-only mode

        if action.context_lines > 0 and not action.files_only:
            cmd += f" -C {action.context_lines}"

        if action.include:
            safe_include = action.include.replace("'", "'\\''")
            cmd += f" --include='{safe_include}'"

        # Exclude dirs
        for d in _EXCLUDE_DIRS:
            cmd += f" --exclude-dir='{d}'"

        cmd += f" '{safe_pattern}' '{safe_path}' 2>/dev/null | head -100"
        return cmd

    def _normalize_search_path(self, path: str) -> str:
        raw_path = (path or "").strip()
        if not raw_path or raw_path in (".", "workspace", "workspace/"):
            return WORKSPACE
        if raw_path == "/workspace":
            return WORKSPACE
        if raw_path.startswith("/workspace/"):
            return f"{WORKSPACE}/{raw_path[len('/workspace/'):]}"
        return raw_path

    def __call__(self, action: GrepAction, conversation=None) -> GrepObservation:
        try:
            if self._has_ripgrep:
                cmd = self._build_ripgrep_cmd(action)
            else:
                cmd = self._build_grep_cmd(action)

            result = self.sandbox.process.exec(cmd, timeout=30)
            output = getattr(result, "result", "") or ""

            matches: list[str] = []
            files: set[str] = set()

            if output.strip():
                for line in output.strip().splitlines():
                    matches.append(line)
                    # Extract file path (before first ":")
                    file_path = line.split(":", 1)[0]
                    if file_path:
                        files.add(file_path)

            return GrepObservation(
                matches=matches,
                files=sorted(files),
                count=len(matches),
                success=True,
                files_only=action.files_only,
            )
        except Exception as e:
            return GrepObservation(
                matches=[str(e)],
                files=[],
                count=0,
                success=False,
            )


class GrepTool(ToolDefinition[GrepAction, GrepObservation]):
    """Search file contents by regex in sandbox."""

    @classmethod
    def create(cls, conv_state, *, sandbox: Sandbox | None = None) -> Sequence[ToolDefinition]:
        if sandbox is None:
            sandbox = conv_state.agent_state.get("sandbox")
        if not sandbox:
            raise ValueError("sandbox not found in conv_state.agent_state")
        executor = GrepExecutor(sandbox)
        return [cls(
            description=_DESCRIPTION,
            action_type=GrepAction,
            observation_type=GrepObservation,
            annotations=ToolAnnotations(
                title="grep",
                readOnlyHint=True,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=False,
            ),
            executor=executor,
        )]
