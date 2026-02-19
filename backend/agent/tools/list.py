# pyright: basic
# type: ignore

from collections.abc import Sequence

from pydantic import Field

from openhands.sdk import Action, Observation, TextContent, ImageContent, ToolDefinition
from openhands.sdk.tool import ToolExecutor

from pathlib import Path

from daytona import Sandbox

_DESCRIPTION = (Path(__file__).parent / "list.txt").read_text(encoding="utf-8").strip()


class FileListAction(Action):
    path: str = Field(description="Absolute directory path inside sandbox to list")


class FileListObservation(Observation):
    listing: str = ""
    success: bool = True

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        prefix = "" if self.success else "FAILED: "
        return [TextContent(text=f"{prefix}{self.listing}")]


class FileListExecutor(ToolExecutor[FileListAction, FileListObservation]):
    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox

    def __call__(self, action: FileListAction, conversation=None) -> FileListObservation:
        try:
            files = self.sandbox.fs.list_files(action.path)
            if not files:
                return FileListObservation(listing=f"{action.path}: (empty directory)", success=True)
            items = []
            for f in files:
                name = getattr(f, "name", str(f))
                is_dir = getattr(f, "is_dir", False)
                icon = "dir" if is_dir else "file"
                items.append(f"  [{icon}] {name}")
            return FileListObservation(
                listing=f"Contents of {action.path}:\n" + "\n".join(items),
                success=True,
            )
        except Exception as e:
            return FileListObservation(listing=str(e), success=False)


class FileListTool(ToolDefinition[FileListAction, FileListObservation]):
    """List directory contents in sandbox."""
    name = "daytona_file_list"

    @classmethod
    def create(cls, conv_state, *, sandbox: Sandbox) -> Sequence[ToolDefinition]:
        executor = FileListExecutor(sandbox)
        return [cls(
            description=_DESCRIPTION,
            action_type=FileListAction,
            observation_type=FileListObservation,
            executor=executor,
        )]
