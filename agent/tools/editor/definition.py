from collections.abc import Sequence
from typing import Literal, Optional

from pydantic import Field

from openhands.sdk import Action, Observation, TextContent, ImageContent, ToolDefinition
from openhands.sdk.tool import ToolExecutor

from daytona import Sandbox


CommandLiteral = Literal["view", "create", "str_replace", "insert", "undo_edit"]

TOOL_DESCRIPTION = """\
Custom editing tool for viewing, creating and editing files in plain-text format.

* State is persistent across command calls and discussions with the user
* If `path` is a file, `view` displays numbered lines. If `path` is a directory, `view` lists files up to 2 levels deep
* The `create` command creates a new file (fails if file already exists)
* The `undo_edit` command reverts the last edit made to the file at `path`
* Always use absolute file paths (starting with /)

CRITICAL REQUIREMENTS:

1. EXACT MATCHING: `old_str` must match EXACTLY one or more consecutive lines, including all whitespace and indentation.
2. UNIQUENESS: `old_str` must uniquely identify a single location. Include 3-5 lines of context.
3. REPLACEMENT: `new_str` replaces `old_str`. Both must be different.

When making multiple edits to the same file, send all edits in a single message.
"""


class FileEditorAction(Action):
    command: CommandLiteral = Field(
        description="The commands to run. Allowed options are: `view`, `create`, "
        "`str_replace`, `insert`, `undo_edit`."
    )
    path: str = Field(description="Absolute path to file or directory inside sandbox")
    file_text: Optional[str] = Field(
        default=None,
        description="[create] Full content to write into the new file.",
    )
    old_str: Optional[str] = Field(
        default=None,
        description="[str_replace] Exact text to find and replace. Must match uniquely.",
    )
    new_str: Optional[str] = Field(
        default=None,
        description="[str_replace] Replacement text. [insert] Text to insert.",
    )
    insert_line: Optional[int] = Field(
        default=None,
        ge=0,
        description="[insert] Line number AFTER which to insert new_str (0 = beginning).",
    )
    view_range: Optional[list[int]] = Field(
        default=None,
        description="[view] Optional [start_line, end_line] (1-indexed). Omit for full file.",
    )


class FileEditorObservation(Observation):
    output: str = ""

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        return [TextContent(text=self.output)]


class FileEditorTool(ToolDefinition[FileEditorAction, FileEditorObservation]):
    """str_replace-style file editor for sandbox."""
    name = "file_editor"

    @classmethod
    def create(cls, conv_state, *, sandbox: Sandbox, file_edits: list | None = None) -> Sequence[ToolDefinition]:
        from .impl import FileEditorExecutor

        executor = FileEditorExecutor(sandbox, file_edits=file_edits)
        return [cls(
            description=TOOL_DESCRIPTION,
            action_type=FileEditorAction,
            observation_type=FileEditorObservation,
            executor=executor,
        )]
