# pyright: basic
# type: ignore

from collections.abc import Sequence

from pydantic import Field

from openhands.sdk import Action, Observation, TextContent, ImageContent, ToolDefinition
from openhands.sdk.tool import ToolExecutor

from pathlib import Path

from daytona import Sandbox

_DESCRIPTION = (Path(__file__).parent / "info.txt").read_text(encoding="utf-8").strip()


class FileInfoAction(Action):
    path: str = Field(description="Absolute path inside sandbox to get info for")


class FileInfoObservation(Observation):
    info: str = ""
    success: bool = True

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        prefix = "" if self.success else "FAILED: "
        return [TextContent(text=f"{prefix}{self.info}")]


class FileInfoExecutor(ToolExecutor[FileInfoAction, FileInfoObservation]):
    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox

    def __call__(self, action: FileInfoAction, conversation=None) -> FileInfoObservation:
        try:
            info = self.sandbox.fs.get_file_info(action.path)
            return FileInfoObservation(info=f"Info for {action.path}:\n{str(info)}", success=True)
        except Exception as e:
            return FileInfoObservation(info=str(e), success=False)


class FileInfoTool(ToolDefinition[FileInfoAction, FileInfoObservation]):
    """Get file/folder metadata in sandbox."""
    name = "daytona_file_info"

    @classmethod
    def create(cls, conv_state, *, sandbox: Sandbox) -> Sequence[ToolDefinition]:
        executor = FileInfoExecutor(sandbox)
        return [cls(
            description=_DESCRIPTION,
            action_type=FileInfoAction,
            observation_type=FileInfoObservation,
            executor=executor,
        )]
