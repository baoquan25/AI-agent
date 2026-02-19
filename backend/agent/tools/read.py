# pyright: basic
# type: ignore

from collections.abc import Sequence

from pydantic import Field

from openhands.sdk import Action, Observation, TextContent, ImageContent, ToolDefinition
from openhands.sdk.tool import ToolExecutor

from pathlib import Path

from daytona import Sandbox

_DESCRIPTION = (Path(__file__).parent / "read.txt").read_text(encoding="utf-8").strip()


class FileReadAction(Action):
    path: str = Field(description="Absolute file path inside sandbox to read")


class FileReadObservation(Observation):
    content: str = ""
    success: bool = True

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        prefix = "" if self.success else "FAILED: "
        return [TextContent(text=f"{prefix}{self.content}")]


class FileReadExecutor(ToolExecutor[FileReadAction, FileReadObservation]):
    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox

    def __call__(self, action: FileReadAction, conversation=None) -> FileReadObservation:
        try:
            content_bytes = self.sandbox.fs.download_file(action.path)
            content = (
                content_bytes.decode("utf-8", errors="replace")
                if isinstance(content_bytes, bytes)
                else str(content_bytes)
            )
            return FileReadObservation(content=f"Content of {action.path}:\n{content}", success=True)
        except Exception as e:
            return FileReadObservation(content=str(e), success=False)


class FileReadTool(ToolDefinition[FileReadAction, FileReadObservation]):
    """Read file content from sandbox."""
    name = "daytona_file_read"

    @classmethod
    def create(cls, conv_state, *, sandbox: Sandbox) -> Sequence[ToolDefinition]:
        executor = FileReadExecutor(sandbox)
        return [cls(
            description=_DESCRIPTION,
            action_type=FileReadAction,
            observation_type=FileReadObservation,
            executor=executor,
        )]
