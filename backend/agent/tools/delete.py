# pyright: basic
# type: ignore

from collections.abc import Sequence

from pydantic import Field

from openhands.sdk import Action, Observation, TextContent, ImageContent, ToolDefinition
from openhands.sdk.tool import ToolExecutor

from pathlib import Path

from daytona import Sandbox

_DESCRIPTION = (Path(__file__).parent / "delete.txt").read_text(encoding="utf-8").strip()


class FileDeleteAction(Action):
    path: str = Field(description="Absolute path inside sandbox to delete")
    recursive: bool = Field(default=False, description="If True, delete directory recursively")


class FileDeleteObservation(Observation):
    result: str = ""
    success: bool = True

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        prefix = "" if self.success else "FAILED: "
        return [TextContent(text=f"{prefix}{self.result}")]


class FileDeleteExecutor(ToolExecutor[FileDeleteAction, FileDeleteObservation]):
    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox

    def __call__(self, action: FileDeleteAction, conversation=None) -> FileDeleteObservation:
        try:
            self.sandbox.fs.delete_file(action.path, recursive=action.recursive)
            return FileDeleteObservation(result=f"Deleted {action.path}", success=True)
        except Exception as e:
            return FileDeleteObservation(result=str(e), success=False)


class FileDeleteTool(ToolDefinition[FileDeleteAction, FileDeleteObservation]):
    """Delete a file or folder in sandbox."""
    name = "daytona_file_delete"

    @classmethod
    def create(cls, conv_state, *, sandbox: Sandbox) -> Sequence[ToolDefinition]:
        executor = FileDeleteExecutor(sandbox)
        return [cls(
            description=_DESCRIPTION,
            action_type=FileDeleteAction,
            observation_type=FileDeleteObservation,
            executor=executor,
        )]
