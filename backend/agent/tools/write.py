# pyright: basic
# type: ignore

from collections.abc import Sequence

from pydantic import Field

from openhands.sdk import Action, Observation, TextContent, ImageContent, ToolDefinition
from openhands.sdk.tool import ToolExecutor

from pathlib import Path

from daytona import Sandbox

_DESCRIPTION = (Path(__file__).parent / "write.txt").read_text(encoding="utf-8").strip()


class FileWriteAction(Action):
    path: str = Field(description="Absolute file path inside sandbox to write to")
    content: str = Field(description="Text content to write into the file")


class FileWriteObservation(Observation):
    result: str = ""
    success: bool = True

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        prefix = "" if self.success else "FAILED: "
        return [TextContent(text=f"{prefix}{self.result}")]


class FileWriteExecutor(ToolExecutor[FileWriteAction, FileWriteObservation]):
    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox

    def __call__(self, action: FileWriteAction, conversation=None) -> FileWriteObservation:
        try:
            content_bytes = action.content.encode("utf-8")
            self.sandbox.fs.upload_file(content_bytes, action.path)
            return FileWriteObservation(
                result=f"Successfully wrote {len(content_bytes)} bytes to {action.path}",
                success=True,
            )
        except Exception as e:
            return FileWriteObservation(result=str(e), success=False)


class FileWriteTool(ToolDefinition[FileWriteAction, FileWriteObservation]):
    """Write/create a file in sandbox."""
    name = "daytona_file_write"

    @classmethod
    def create(cls, conv_state, *, sandbox: Sandbox) -> Sequence[ToolDefinition]:
        executor = FileWriteExecutor(sandbox)
        return [cls(
            description=_DESCRIPTION,
            action_type=FileWriteAction,
            observation_type=FileWriteObservation,
            executor=executor,
        )]
