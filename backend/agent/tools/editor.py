# pyright: basic
# type: ignore

from collections.abc import Sequence
from typing import Optional

from pydantic import Field

from openhands.sdk import Action, Observation, TextContent, ImageContent, ToolDefinition
from openhands.sdk.tool import ToolExecutor

from pathlib import Path

from daytona import Sandbox

_DESCRIPTION = (Path(__file__).parent / "editor.txt").read_text(encoding="utf-8").strip()


# ── Action ──────────────────────────────────────────────────────────

class FileEditorAction(Action):
    """str_replace-style file editor action."""
    command: str = Field(
        description="One of: 'view', 'str_replace', 'insert', 'undo'"
    )
    path: str = Field(
        description="Absolute file path inside the sandbox"
    )
    old_str: Optional[str] = Field(
        default=None,
        description="[str_replace] Exact text to find and replace. Must match uniquely."
    )
    new_str: Optional[str] = Field(
        default=None,
        description="[str_replace] Replacement text. [insert] Text to insert."
    )
    insert_line: Optional[int] = Field(
        default=None,
        description="[insert] Line number after which to insert new_str (0 = beginning of file)."
    )
    view_range: Optional[list[int]] = Field(
        default=None,
        description="[view] Optional [start_line, end_line] (1-indexed). Omit to view entire file."
    )


# ── Observation ─────────────────────────────────────────────────────

class FileEditorObservation(Observation):
    output: str = ""
    success: bool = True

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        prefix = "" if self.success else "FAILED: "
        return [TextContent(text=f"{prefix}{self.output}")]


# ── Executor ────────────────────────────────────────────────────────

class FileEditorExecutor(ToolExecutor[FileEditorAction, FileEditorObservation]):
    """
    Implements str_replace editor commands by proxying through Daytona sandbox fs.
    Maintains an undo buffer (last version of each edited file).
    """

    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox
        self._undo_buffer: dict[str, str] = {}

    def _read_file(self, path: str) -> str:
        content_bytes = self.sandbox.fs.download_file(path)
        if isinstance(content_bytes, bytes):
            return content_bytes.decode("utf-8", errors="replace")
        return str(content_bytes)

    def _write_file(self, path: str, content: str) -> None:
        self.sandbox.fs.upload_file(content.encode("utf-8"), path)

    def __call__(self, action: FileEditorAction, conversation=None) -> FileEditorObservation:
        try:
            cmd = action.command.lower().strip()
            if cmd == "view":
                return self._cmd_view(action)
            elif cmd == "str_replace":
                return self._cmd_str_replace(action)
            elif cmd == "insert":
                return self._cmd_insert(action)
            elif cmd == "undo":
                return self._cmd_undo(action)
            else:
                return FileEditorObservation(
                    output=f"Unknown command '{cmd}'. Use: view, str_replace, insert, undo",
                    success=False,
                )
        except Exception as e:
            return FileEditorObservation(output=str(e), success=False)

    def _cmd_view(self, action: FileEditorAction) -> FileEditorObservation:
        content = self._read_file(action.path)
        lines = content.splitlines(keepends=True)
        total = len(lines)

        if action.view_range:
            start = max(1, action.view_range[0])
            end = min(total, action.view_range[1]) if len(action.view_range) > 1 else total
            selected = lines[start - 1 : end]
            header = f"[Viewing {action.path} lines {start}-{end} of {total}]\n"
        else:
            selected = lines
            header = f"[Viewing {action.path} ({total} lines)]\n"

        numbered = ""
        offset = (action.view_range[0] if action.view_range else 1)
        for i, line in enumerate(selected):
            numbered += f"{offset + i:6}\t{line}"

        return FileEditorObservation(output=header + numbered, success=True)

    def _cmd_str_replace(self, action: FileEditorAction) -> FileEditorObservation:
        if action.old_str is None:
            return FileEditorObservation(output="old_str is required for str_replace", success=False)
        if action.new_str is None:
            return FileEditorObservation(output="new_str is required for str_replace", success=False)

        content = self._read_file(action.path)

        count = content.count(action.old_str)
        if count == 0:
            return FileEditorObservation(
                output=f"old_str not found in {action.path}. Make sure it matches exactly (including whitespace).",
                success=False,
            )
        if count > 1:
            return FileEditorObservation(
                output=f"old_str found {count} times in {action.path}. It must be unique. Add more context to old_str.",
                success=False,
            )

        self._undo_buffer[action.path] = content
        new_content = content.replace(action.old_str, action.new_str, 1)
        self._write_file(action.path, new_content)

        new_lines = new_content.splitlines()
        old_lines = content.splitlines()
        changed_line = 0
        for i, (o, n) in enumerate(zip(old_lines, new_lines)):
            if o != n:
                changed_line = i + 1
                break
        else:
            changed_line = min(len(old_lines), len(new_lines))

        start = max(0, changed_line - 4)
        end = min(len(new_lines), changed_line + 3)
        snippet_lines = []
        for i in range(start, end):
            snippet_lines.append(f"{i + 1:6}\t{new_lines[i]}")
        snippet = "\n".join(snippet_lines)

        return FileEditorObservation(
            output=f"Replaced in {action.path}.\n\n{snippet}",
            success=True,
        )

    def _cmd_insert(self, action: FileEditorAction) -> FileEditorObservation:
        if action.insert_line is None:
            return FileEditorObservation(output="insert_line is required for insert", success=False)
        if action.new_str is None:
            return FileEditorObservation(output="new_str is required for insert", success=False)

        content = self._read_file(action.path)
        self._undo_buffer[action.path] = content

        lines = content.splitlines(keepends=True)
        insert_at = max(0, min(action.insert_line, len(lines)))

        new_text = action.new_str
        if not new_text.endswith("\n"):
            new_text += "\n"

        lines.insert(insert_at, new_text)
        new_content = "".join(lines)
        self._write_file(action.path, new_content)

        new_lines = new_content.splitlines()
        start = max(0, insert_at - 2)
        end = min(len(new_lines), insert_at + 5)
        snippet_lines = []
        for i in range(start, end):
            snippet_lines.append(f"{i + 1:6}\t{new_lines[i]}")
        snippet = "\n".join(snippet_lines)

        return FileEditorObservation(
            output=f"Inserted at line {insert_at + 1} in {action.path}.\n\n{snippet}",
            success=True,
        )

    def _cmd_undo(self, action: FileEditorAction) -> FileEditorObservation:
        prev = self._undo_buffer.pop(action.path, None)
        if prev is None:
            return FileEditorObservation(
                output=f"No undo history for {action.path}",
                success=False,
            )
        self._write_file(action.path, prev)
        return FileEditorObservation(
            output=f"Reverted {action.path} to previous version.",
            success=True,
        )


class FileEditorTool(ToolDefinition[FileEditorAction, FileEditorObservation]):
    """str_replace-style file editor for Daytona sandbox."""
    name = "daytona_file_editor"

    @classmethod
    def create(cls, conv_state, *, sandbox: Sandbox) -> Sequence[ToolDefinition]:
        executor = FileEditorExecutor(sandbox)
        return [cls(
            description=_DESCRIPTION,
            action_type=FileEditorAction,
            observation_type=FileEditorObservation,
            executor=executor,
        )]
