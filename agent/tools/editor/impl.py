# pyright: basic
# type: ignore

"""Executor that bridges the OpenHands ToolExecutor interface with DaytonaFileEditor."""

from openhands.sdk.tool import ToolExecutor

from daytona import Sandbox

from .definition import FileEditorAction, FileEditorObservation
from .editor import DaytonaFileEditor
from .exceptions import ToolError


class DaytonaFileEditorExecutor(ToolExecutor[FileEditorAction, FileEditorObservation]):
    """Wraps DaytonaFileEditor as an OpenHands ToolExecutor."""

    def __init__(self, sandbox: Sandbox, file_edits: list | None = None):
        self.editor = DaytonaFileEditor(sandbox, file_edits=file_edits)

    def __call__(
        self,
        action: FileEditorAction,
        conversation=None,
    ) -> FileEditorObservation:
        try:
            return self.editor(
                command=action.command,
                path=action.path,
                file_text=action.file_text,
                view_range=action.view_range,
                old_str=action.old_str,
                new_str=action.new_str,
                insert_line=action.insert_line,
            )
        except ToolError as e:
            return FileEditorObservation(output=e.message)
        except Exception as e:
            return FileEditorObservation(output=str(e))
