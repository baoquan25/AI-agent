# pyright: basic
# type: ignore

from collections.abc import Sequence
from typing import Optional

from pydantic import Field

from openhands.sdk import Action, Observation, TextContent, ImageContent, ToolDefinition
from openhands.sdk.tool import ToolAnnotations, ToolExecutor

from daytona import Sandbox
from dependencies import WORKSPACE


TOOL_DESCRIPTION = """Fast file pattern matching tool.
* Supports glob patterns like "**/*.js" or "src/**/*.ts"
* Returns matching file paths sorted by modification time
* Use this tool when you need to find files by name patterns
* Only the first 100 results are returned. Consider narrowing your search with stricter
  glob patterns or provide path parameter if you need more results.

Examples:
- Find all JavaScript files: "**/*.js"
- Find TypeScript files in src: "src/**/*.ts"
- Find Python test files: "**/test_*.py"
- Find configuration files: "**/*.{json,yaml,yml,toml}"
"""


class GlobAction(Action):
    pattern: str = Field(
        description='The glob pattern to match files (e.g., "**/*.js", "src/**/*.ts")'
    )
    path: Optional[str] = Field(
        default=None,
        description=f"Absolute directory path to search in. Defaults to {WORKSPACE}.",
    )


class GlobObservation(Observation):
    files: list[str] = Field(default_factory=list)
    pattern: str = ""
    search_path: str = ""
    truncated: bool = False
    success: bool = True

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        if not self.success:
            return [TextContent(text=f"FAILED: {self.files[0] if self.files else 'unknown error'}")]
        if not self.files:
            return [TextContent(text=f"No files matching '{self.pattern}' in {self.search_path}")]
        items = "\n".join(f"  {f}" for f in self.files)
        trunc = " (truncated to 100)" if self.truncated else ""
        return [TextContent(
            text=f"Found {len(self.files)} file(s) matching '{self.pattern}'{trunc}:\n{items}"
        )]


def _extract_search_path(pattern: str, default: str) -> tuple[str, str]:
    """Split absolute path pattern into (search_path, relative_pattern).

    Examples:
        "/workspace/src/**/*.py" → ("/workspace/src", "**/*.py")
        "**/*.js"                → (default, "**/*.js")
        "*.py"                   → (default, "*.py")
    """
    if not pattern or not pattern.startswith("/"):
        return default, pattern

    # Walk parts until we hit a glob character
    parts = pattern.split("/")
    search_parts: list[str] = []
    for i, part in enumerate(parts):
        if any(c in part for c in ("*", "?", "[", "{")):
            remaining = "/".join(parts[i:])
            break
        search_parts.append(part)
    else:
        # No glob chars found — treat entire pattern as path, match everything
        return pattern, "**/*"

    search_path = "/".join(search_parts) or "/"
    return search_path, remaining


class GlobExecutor(ToolExecutor[GlobAction, GlobObservation]):
    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox
        # Check ripgrep availability once
        rg_check = self.sandbox.process.exec("which rg 2>/dev/null", timeout=5)
        self._has_ripgrep = bool(getattr(rg_check, "result", "").strip())

    def __call__(self, action: GlobAction, conversation=None) -> GlobObservation:
        try:
            original_pattern = action.pattern
            default_path = self._normalize_search_path(action.path or WORKSPACE)

            # Extract search path from absolute patterns like /workspace/src/**/*.py
            search_path, pattern = _extract_search_path(original_pattern, default_path)
            if action.path:
                # Explicit path overrides extraction
                search_path = self._normalize_search_path(action.path)
                pattern = original_pattern

            search_path = self._normalize_search_path(search_path)

            safe_path = search_path.replace("'", "'\\''")
            safe_pattern = pattern.replace("'", "'\\''")

            if self._has_ripgrep:
                # ripgrep: fast, sorts by mtime
                cmd = f"rg --files '{safe_path}' -g '{safe_pattern}' --sortr=modified 2>/dev/null | head -100"
            else:
                # find fallback: sort by mtime (newest first)
                cmd = f"find '{safe_path}' -name '{safe_pattern}' -type f -printf '%T@ %p\\n' 2>/dev/null | sort -rn | head -100 | cut -d' ' -f2-"

            result = self.sandbox.process.exec(cmd, timeout=30)
            output = getattr(result, "result", "") or ""

            files = [line.strip() for line in output.strip().splitlines() if line.strip()]
            truncated = len(files) >= 100

            return GlobObservation(
                files=files,
                pattern=original_pattern,
                search_path=search_path,
                truncated=truncated,
                success=True,
            )
        except Exception as e:
            return GlobObservation(
                files=[str(e)],
                pattern=action.pattern,
                search_path=self._normalize_search_path(action.path or WORKSPACE),
                success=False,
            )

    def _normalize_search_path(self, path: str) -> str:
        raw_path = (path or "").strip()
        if not raw_path or raw_path in (".", "workspace", "workspace/"):
            return WORKSPACE
        if raw_path == "/workspace":
            return WORKSPACE
        if raw_path.startswith("/workspace/"):
            return f"{WORKSPACE}/{raw_path[len('/workspace/'):]}"
        return raw_path


class GlobTool(ToolDefinition[GlobAction, GlobObservation]):
    """Fast file pattern matching in sandbox."""

    @classmethod
    def create(cls, conv_state, *, sandbox: Sandbox | None = None) -> Sequence[ToolDefinition]:
        if sandbox is None:
            sandbox = conv_state.agent_state.get("sandbox")
        if not sandbox:
            raise ValueError("sandbox not found in conv_state.agent_state")
        executor = GlobExecutor(sandbox)
        return [cls(
            description=TOOL_DESCRIPTION,
            action_type=GlobAction,
            observation_type=GlobObservation,
            annotations=ToolAnnotations(
                title="glob",
                readOnlyHint=True,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=False,
            ),
            executor=executor,
        )]
