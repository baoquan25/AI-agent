# pyright: basic
# type: ignore

from collections.abc import Sequence
from typing import Optional

from pydantic import Field

from openhands.sdk import Action, Observation, TextContent, ImageContent, ToolDefinition
from openhands.sdk.tool import ToolExecutor

from pathlib import Path

from daytona import Sandbox

_DESCRIPTION = """
Search for text or regex patterns INSIDE file contents in the sandbox.
This is like `grep -rn` — it finds which files contain the pattern and shows matching lines.

**When to use:**
* Find where a function/class/variable is defined or used
* Search for error messages, TODOs, or specific strings
* Find all imports of a module

**Parameters:**
* pattern: Regex or text to search for (e.g. "def calculate", "import os", "TODO")
* path: Directory to search in (default: /workspace, searches recursively)
* include: Optional file filter glob (e.g. "*.py", "*.js")

**Examples:**
```
# Find all files containing "calculate_total"
pattern="calculate_total", path="/workspace"

# Find Python files with "import pandas"
pattern="import pandas", path="/workspace", include="*.py"

# Find class definitions
pattern="class .*Controller", include="*.py"
```

**Output format:** filepath:line_number:matching_line
Only the first 100 results are returned.
"""


class GrepAction(Action):
    pattern: str = Field(description="Regex or text pattern to search for inside files")
    path: str = Field(
        default="/workspace",
        description="Absolute directory path to search in (searches recursively)",
    )
    include: Optional[str] = Field(
        default=None,
        description="Optional glob to filter files (e.g. '*.py', '*.{ts,tsx}')",
    )


class GrepObservation(Observation):
    matches: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    count: int = 0
    success: bool = True

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        if not self.success:
            return [TextContent(text=f"FAILED: {self.matches[0] if self.matches else 'unknown error'}")]
        if self.count == 0:
            return [TextContent(text="No matches found.")]
        files_list = "\n".join(f"  - {f}" for f in self.files[:20])
        sample = "\n".join(self.matches[:30])
        more = "\n  ... (truncated)" if self.count > 30 else ""
        return [TextContent(
            text=f"Found {self.count} matching line(s) in {len(self.files)} file(s).\n\n"
                 f"Files:\n{files_list}\n\n"
                 f"Matches:\n{sample}{more}"
        )]


class GrepExecutor(ToolExecutor[GrepAction, GrepObservation]):
    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox

    def __call__(self, action: GrepAction, conversation=None) -> GrepObservation:
        try:
            cmd = "grep -rHnE"

            if action.include:
                cmd += f" --include='{action.include}'"

            safe_pattern = action.pattern.replace("'", "'\\''")
            safe_path = action.path.replace("'", "'\\''")

            cmd += f" '{safe_pattern}' '{safe_path}' 2>/dev/null | head -100"

            result = self.sandbox.process.exec(cmd, timeout=30)

            output = getattr(result, "result", "") or ""

            matches: list[str] = []
            files: set[str] = set()

            if output.strip():
                for line in output.strip().splitlines():
                    matches.append(line)
                    file_path = line.split(":", 1)[0]
                    if file_path:
                        files.add(file_path)

            return GrepObservation(
                matches=matches,
                files=sorted(files),
                count=len(matches),
                success=True,
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
    name = "grep"

    @classmethod
    def create(cls, conv_state, *, sandbox: Sandbox) -> Sequence[ToolDefinition]:
        executor = GrepExecutor(sandbox)
        return [cls(
            description=_DESCRIPTION,
            action_type=GrepAction,
            observation_type=GrepObservation,
            executor=executor,
        )]
