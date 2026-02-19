# pyright: basic
# type: ignore

from collections.abc import Sequence

from pydantic import Field

from openhands.sdk import Action, Observation, TextContent, ImageContent, ToolDefinition
from openhands.sdk.tool import ToolExecutor

from pathlib import Path

from daytona import Sandbox

_DESCRIPTION = (Path(__file__).parent / "folder.txt").read_text(encoding="utf-8").strip()


class CreateFolderAction(Action):
    path: str = Field(description="Absolute folder path inside sandbox to create")


class CreateFolderObservation(Observation):
    result: str = ""
    success: bool = True

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        prefix = "" if self.success else "FAILED: "
        return [TextContent(text=f"{prefix}{self.result}")]


class CreateFolderExecutor(ToolExecutor[CreateFolderAction, CreateFolderObservation]):
    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox

    def __call__(self, action: CreateFolderAction, conversation=None) -> CreateFolderObservation:
        try:
            self.sandbox.fs.create_folder(action.path, "755")
            return CreateFolderObservation(result=f"Created folder {action.path}", success=True)
        except Exception as e:
            return CreateFolderObservation(result=str(e), success=False)


class CreateFolderTool(ToolDefinition[CreateFolderAction, CreateFolderObservation]):
    """Create a folder in sandbox."""
    name = "daytona_create_folder"

    @classmethod
    def create(cls, conv_state, *, sandbox: Sandbox) -> Sequence[ToolDefinition]:
        executor = CreateFolderExecutor(sandbox)
        return [cls(
            description=_DESCRIPTION,
            action_type=CreateFolderAction,
            observation_type=CreateFolderObservation,
            executor=executor,
        )]
