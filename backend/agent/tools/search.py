# pyright: basic
# type: ignore

from collections.abc import Sequence

from pydantic import Field

from openhands.sdk import Action, Observation, TextContent, ImageContent, ToolDefinition
from openhands.sdk.tool import ToolExecutor

from pathlib import Path

from daytona import Sandbox

_DESCRIPTION = (Path(__file__).parent / "search.txt").read_text(encoding="utf-8").strip()


class FileSearchAction(Action):
    path: str = Field(description="Absolute directory path to search in")
    pattern: str = Field(description="Glob or regex pattern to match files (e.g. '*.py', '**/*.txt')")


class FileSearchObservation(Observation):
    matches: list[str] = Field(default_factory=list)
    count: int = 0
    success: bool = True

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        if not self.success:
            return [TextContent(text=f"FAILED: search error")]
        if self.count == 0:
            return [TextContent(text="No matches found.")]
        items = "\n".join(f"  - {m}" for m in self.matches[:50])
        more = "\n  ... (truncated)" if self.count > 50 else ""
        return [TextContent(text=f"Found {self.count} match(es):\n{items}{more}")]


class FileSearchExecutor(ToolExecutor[FileSearchAction, FileSearchObservation]):
    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox

    def __call__(self, action: FileSearchAction, conversation=None) -> FileSearchObservation:
        try:
            matches = self.sandbox.fs.search_files(action.path, action.pattern)
            match_list = list(matches) if matches else []
            return FileSearchObservation(matches=match_list, count=len(match_list), success=True)
        except Exception as e:
            return FileSearchObservation(matches=[str(e)], count=0, success=False)


class FileSearchTool(ToolDefinition[FileSearchAction, FileSearchObservation]):
    """Search files by pattern in sandbox."""
    name = "daytona_file_search"

    @classmethod
    def create(cls, conv_state, *, sandbox: Sandbox) -> Sequence[ToolDefinition]:
        executor = FileSearchExecutor(sandbox)
        return [cls(
            description=_DESCRIPTION,
            action_type=FileSearchAction,
            observation_type=FileSearchObservation,
            executor=executor,
        )]
