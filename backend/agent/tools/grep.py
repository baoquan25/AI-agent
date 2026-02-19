# pyright: basic
# type: ignore

"""
GrepTool — Search content inside files (grep-like).

Khác với file_search.py (tìm FILE theo tên/glob),
tool này tìm NỘI DUNG bên trong file theo regex.

Ví dụ:
  file_search: pattern="*.py"         → danh sách file .py
  grep:        pattern="import os"    → dòng nào chứa "import os", ở file nào, dòng mấy
"""

from collections.abc import Sequence
from typing import Optional

from pydantic import Field

from openhands.sdk import Action, Observation, TextContent, ImageContent, ToolDefinition
from openhands.sdk.tool import ToolExecutor

from pathlib import Path

from daytona import Sandbox

_DESCRIPTION = (Path(__file__).parent / "grep.txt").read_text(encoding="utf-8").strip()


# ── Action ──────────────────────────────────────────────────────────

class GrepAction(Action):
    pattern: str = Field(description="Regex or text pattern to search for inside files")
    path: str = Field(
        default="/home/daytona/workspace",
        description="Absolute directory path to search in (searches recursively)",
    )
    include: Optional[str] = Field(
        default=None,
        description="Optional glob to filter files (e.g. '*.py', '*.{ts,tsx}')",
    )


# ── Observation ─────────────────────────────────────────────────────

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


# ── Executor ────────────────────────────────────────────────────────

class GrepExecutor(ToolExecutor[GrepAction, GrepObservation]):
    """
    Runs grep via sandbox.process.exec to search file contents.
    Uses grep -rHnE (recursive, show filename, line number, extended regex).
    """

    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox

    def __call__(self, action: GrepAction, conversation=None) -> GrepObservation:
        try:
            # Build grep command
            # -r: recursive, -H: show filename, -n: line numbers, -E: extended regex
            cmd = "grep -rHnE"

            if action.include:
                cmd += f" --include='{action.include}'"

            # Escape single quotes in pattern
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
                    # Format: "filepath:linenum:content"
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
    name = "daytona_grep"

    @classmethod
    def create(cls, conv_state, *, sandbox: Sandbox) -> Sequence[ToolDefinition]:
        executor = GrepExecutor(sandbox)
        return [cls(
            description=_DESCRIPTION,
            action_type=GrepAction,
            observation_type=GrepObservation,
            executor=executor,
        )]
