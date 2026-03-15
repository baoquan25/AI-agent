# pyright: basic
# type: ignore

"""Glob tool — find files by glob pattern via sandbox.process.exec."""

from collections.abc import Sequence
from typing import Optional

from pydantic import Field

from openhands.sdk import Action, Observation, TextContent, ImageContent, ToolDefinition
from openhands.sdk.tool import ToolExecutor

from daytona import Sandbox


TOOL_DESCRIPTION = """
*  Fast file pattern matching tool that works with any codebase size
*  Supports glob patterns like "**/*.js" or "src/**/*.ts"
*  Returns matching file paths sorted by modification time
*  Use this tool when you need to find files by name patterns
*  When you are doing an open-ended search that may require multiple rounds of globbing and grepping, use the Task tool instead
*  You have the capability to call multiple tools in a single response. It is always better to speculatively
*  Only the first 100 results are returned.

Examples:
- Find all JavaScript files: "**/*.js"
- Find TypeScript files in src: "src/**/*.ts"
- Find Python test files: "**/test_*.py"
- Find configuration files: "**/*.{json,yaml,yml,toml}"
"""


class DaytonaGlobAction(Action):
    pattern: str = Field(
        description='The glob pattern to match files (e.g., "**/*.js", "src/**/*.ts")'
    )
    path: Optional[str] = Field(
        default="/home/daytona/workspace",
        description="The directory to search in. Defaults to workspace root.",
    )


class DaytonaGlobObservation(Observation):
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


class GlobExecutor(ToolExecutor[DaytonaGlobAction, DaytonaGlobObservation]):
    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox

    def __call__(self, action: DaytonaGlobAction, conversation=None) -> DaytonaGlobObservation:
        try:
            search_path = action.path or "/home/daytona/workspace"
            safe_path = search_path.replace("'", "'\\''")
            safe_pattern = action.pattern.replace("'", "'\\''")

            cmd = f"find '{safe_path}' -name '{safe_pattern}' -type f 2>/dev/null | head -100"
            result = self.sandbox.process.exec(cmd, timeout=30)
            output = getattr(result, "result", "") or ""

            files = [line.strip() for line in output.strip().splitlines() if line.strip()]
            truncated = len(files) >= 100

            return DaytonaGlobObservation(
                files=files,
                pattern=action.pattern,
                search_path=search_path,
                truncated=truncated,
                success=True,
            )
        except Exception as e:
            return DaytonaGlobObservation(
                files=[str(e)],
                pattern=action.pattern,
                search_path=action.path or "/home/daytona/workspace",
                success=False,
            )


class GlobTool(ToolDefinition[DaytonaGlobAction, DaytonaGlobObservation]):
    """Find files by glob pattern in sandbox."""
    name = "daytona_glob"

    @classmethod
    def create(cls, conv_state, *, sandbox: Sandbox) -> Sequence[ToolDefinition]:
        executor = GlobExecutor(sandbox)
        return [cls(
            description=TOOL_DESCRIPTION,
            action_type=DaytonaGlobAction,
            observation_type=DaytonaGlobObservation,
            executor=executor,
        )]
