import logging
import posixpath
import re
from typing import get_args

from daytona import Sandbox

from .definition import CommandLiteral, FileEditorObservation
from .exceptions import (
    EditorToolParameterInvalidError,
    EditorToolParameterMissingError,
    ToolError,
)
from .utils.config import SNIPPET_CONTEXT_WINDOW
from tools.notify import notify_file_change
from .utils.constants import MAX_RESPONSE_LEN_CHAR, TEXT_FILE_CONTENT_TRUNCATED_NOTICE

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
SNIPPET_CONTEXT = SNIPPET_CONTEXT_WINDOW


def _maybe_truncate(text: str, max_len: int = MAX_RESPONSE_LEN_CHAR) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n{TEXT_FILE_CONTENT_TRUNCATED_NOTICE}"


class FileEditor:

    def __init__(self, sandbox: Sandbox, max_history: int = 10, file_edits: list | None = None):
        self.sandbox = sandbox
        self._history: dict[str, list[str]] = {}
        self._max_history = max_history
        self._file_edits = file_edits

    # ── Sandbox I/O layer ────────────────────────────────────────────

    def _read_file(self, path: str) -> str:
        raw = self.sandbox.fs.download_file(path)
        if isinstance(raw, bytes):
            return raw.decode("utf-8", errors="replace")
        return str(raw)

    def _write_file(self, path: str, content: str) -> None:
        data = content.encode("utf-8")
        try:
            self.sandbox.fs.upload_file(data, path)
        except Exception:
            parent = posixpath.dirname(path)
            if parent and parent != "/":
                try:
                    self.sandbox.fs.create_folder(parent, "755")
                except Exception:
                    pass
            self.sandbox.fs.upload_file(data, path)

    def _file_exists(self, path: str) -> bool:
        try:
            self.sandbox.fs.get_file_info(path)
            return True
        except Exception:
            return False

    def _is_dir(self, path: str) -> bool:
        try:
            info = self.sandbox.fs.get_file_info(path)
            return getattr(info, "is_dir", False)
        except Exception:
            return False

    def _get_file_size(self, path: str) -> int:
        try:
            info = self.sandbox.fs.get_file_info(path)
            return getattr(info, "size", 0)
        except Exception:
            return 0

    # ── History (in-memory) ──────────────────────────────────────────

    def _push_history(self, path: str, content: str) -> None:
        if path not in self._history:
            self._history[path] = []
        self._history[path].append(content)
        if len(self._history[path]) > self._max_history:
            self._history[path] = self._history[path][-self._max_history:]

    def _pop_history(self, path: str) -> str | None:
        entries = self._history.get(path)
        if entries:
            return entries.pop()
        return None

    def _track_edit(self, path: str, action: str, old_content: str | None, new_content: str | None) -> None:
        if self._file_edits is None:
            return
        for entry in self._file_edits:
            if entry["path"] == path:
                entry["new_content"] = new_content
                entry["action"] = action
                return
        self._file_edits.append({
            "path": path,
            "action": action,
            "old_content": old_content,
            "new_content": new_content,
        })

    # ── Dispatcher ───────────────────────────────────────────────────

    def __call__(
        self,
        *,
        command: CommandLiteral,
        path: str,
        file_text: str | None = None,
        view_range: list[int] | None = None,
        old_str: str | None = None,
        new_str: str | None = None,
        insert_line: int | None = None,
    ) -> FileEditorObservation:
        self._validate_path(command, path)

        if command == "view":
            return self._cmd_view(path, view_range)
        elif command == "create":
            if file_text is None:
                raise EditorToolParameterMissingError(command, "file_text")
            return self._cmd_create(path, file_text)
        elif command == "str_replace":
            if old_str is None:
                raise EditorToolParameterMissingError(command, "old_str")
            if new_str is None:
                raise EditorToolParameterMissingError(command, "new_str")
            if old_str == new_str:
                raise EditorToolParameterInvalidError(
                    "new_str", new_str,
                    "No replacement was performed. `new_str` and `old_str` must be different.",
                )
            return self._cmd_str_replace(path, old_str, new_str)
        elif command == "insert":
            if insert_line is None:
                raise EditorToolParameterMissingError(command, "insert_line")
            if new_str is None:
                raise EditorToolParameterMissingError(command, "new_str")
            return self._cmd_insert(path, insert_line, new_str)
        elif command == "undo_edit":
            return self._cmd_undo(path)

        raise ToolError(
            f"Unrecognized command '{command}'. "
            f"Allowed: {', '.join(get_args(CommandLiteral))}"
        )

    # ── view ─────────────────────────────────────────────────────────

    def _cmd_view(self, path: str, view_range: list[int] | None) -> FileEditorObservation:
        if self._is_dir(path):
            if view_range:
                raise EditorToolParameterInvalidError(
                    "view_range", str(view_range),
                    "view_range is not allowed when path points to a directory.",
                )
            return self._view_directory(path)

        content = self._read_file(path)
        lines = content.splitlines()
        total = len(lines)

        if not view_range:
            output = self._make_output(content, str(path), start_line=1)
            return FileEditorObservation(output=output)

        if len(view_range) != 2 or not all(isinstance(i, int) for i in view_range):
            raise EditorToolParameterInvalidError(
                "view_range", str(view_range),
                "It should be a list of two integers.",
            )

        start, end = view_range
        if start < 1 or start > total:
            raise EditorToolParameterInvalidError(
                "view_range", str(view_range),
                f"start_line {start} is out of range [1, {total}].",
            )
        if end == -1:
            end = total
        elif end > total:
            end = total
        if end < start:
            raise EditorToolParameterInvalidError(
                "view_range", str(view_range),
                f"end_line {end} must be >= start_line {start}.",
            )

        selected = "\n".join(lines[start - 1 : end])
        output = self._make_output(selected, str(path), start_line=start)
        return FileEditorObservation(output=output)

    def _view_directory(self, path: str) -> FileEditorObservation:
        safe_path = path.replace("'", "'\\''")
        cmd = (
            f"find -L '{safe_path}' -maxdepth 2 "
            f"-not \\( -path '{safe_path}/\\.*' -o -path '{safe_path}/*/\\.*' \\) "
            f"2>/dev/null | sort | head -200"
        )
        result = self.sandbox.process.exec(cmd, timeout=15)
        stdout = getattr(result, "result", "") or ""

        if not stdout.strip():
            return FileEditorObservation(
                output=f"{path}/\n  (empty directory)",
            )

        entries = stdout.strip().splitlines()
        formatted = []
        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue
            if self._is_dir(entry):
                formatted.append(f"{entry}/")
            else:
                formatted.append(entry)

        output = (
            f"Files and directories up to 2 levels deep in {path}, "
            f"excluding hidden items:\n" + "\n".join(formatted)
        )
        return FileEditorObservation(output=output)

    # ── create ───────────────────────────────────────────────────────

    def _cmd_create(self, path: str, file_text: str) -> FileEditorObservation:
        self._write_file(path, file_text)
        self._track_edit(path, "create", None, file_text)
        notify_file_change(path, "added")
        num_lines = len(file_text.splitlines())
        size = len(file_text.encode("utf-8"))
        return FileEditorObservation(
            output=f"File created successfully at: {path} ({num_lines} lines, {size} bytes)",
        )

    # ── str_replace (with regex matching + whitespace fallback) ──────

    def _cmd_str_replace(self, path: str, old_str: str, new_str: str) -> FileEditorObservation:
        content = self._read_file(path)

        pattern = re.escape(old_str)
        occurrences = [
            (
                content.count("\n", 0, m.start()) + 1,
                m.group(),
                m.start(),
            )
            for m in re.finditer(pattern, content)
        ]

        if not occurrences:
            old_stripped = old_str.strip()
            new_str = new_str.strip()
            pattern = re.escape(old_stripped)
            occurrences = [
                (
                    content.count("\n", 0, m.start()) + 1,
                    m.group(),
                    m.start(),
                )
                for m in re.finditer(pattern, content)
            ]
            if not occurrences:
                raise ToolError(
                    f"No replacement was performed, old_str did not appear "
                    f"verbatim in {path}."
                )

        if len(occurrences) > 1:
            line_numbers = sorted({line for line, _, _ in occurrences})
            raise ToolError(
                f"No replacement was performed. Multiple occurrences of old_str "
                f"in lines {line_numbers}. Please ensure it is unique."
            )

        replacement_line, matched_text, idx = occurrences[0]

        self._push_history(path, content)
        new_content = content[:idx] + new_str + content[idx + len(matched_text):]
        self._write_file(path, new_content)
        self._track_edit(path, "update", content, new_content)
        notify_file_change(path, "updated")

        start_line = max(0, replacement_line - SNIPPET_CONTEXT)
        end_line = replacement_line + SNIPPET_CONTEXT + new_str.count("\n")
        new_lines = new_content.splitlines()
        snippet = "\n".join(new_lines[start_line:end_line])

        output = f"The file {path} has been edited. "
        output += self._make_output(snippet, f"a snippet of {path}", start_line + 1)
        output += "Review the changes and make sure they are as expected."
        return FileEditorObservation(output=output)

    # ── insert ───────────────────────────────────────────────────────

    def _cmd_insert(self, path: str, insert_line: int, new_str: str) -> FileEditorObservation:
        content = self._read_file(path)
        lines = content.splitlines(keepends=True)
        num_lines = len(lines)

        if insert_line < 0 or insert_line > num_lines:
            raise EditorToolParameterInvalidError(
                "insert_line", str(insert_line),
                f"Must be in range [0, {num_lines}].",
            )

        self._push_history(path, content)

        new_str_lines = new_str.split("\n")
        new_lines_to_insert = [line + "\n" for line in new_str_lines]

        result_lines = lines[:insert_line] + new_lines_to_insert + lines[insert_line:]
        new_content = "".join(result_lines)
        self._write_file(path, new_content)
        self._track_edit(path, "update", content, new_content)
        notify_file_change(path, "updated")

        all_new_lines = new_content.splitlines()
        start = max(0, insert_line - SNIPPET_CONTEXT)
        end = min(
            len(all_new_lines),
            insert_line + SNIPPET_CONTEXT + len(new_str_lines),
        )
        snippet = "\n".join(all_new_lines[start:end])

        output = f"The file {path} has been edited. "
        output += self._make_output(
            snippet, "a snippet of the edited file", max(1, start + 1)
        )
        output += "Review the changes and make sure they are as expected."
        return FileEditorObservation(output=output)

    # ── undo_edit ────────────────────────────────────────────────────

    def _cmd_undo(self, path: str) -> FileEditorObservation:
        old_content = self._pop_history(path)
        if old_content is None:
            raise ToolError(f"No edit history found for {path}.")

        self._write_file(path, old_content)
        notify_file_change(path, "updated")
        output = f"Last edit to {path} undone successfully. "
        output += self._make_output(old_content, str(path))
        return FileEditorObservation(output=output)

    # ── Validation ───────────────────────────────────────────────────

    def _validate_path(self, command: str, path: str) -> None:
        if not path.startswith("/"):
            raise EditorToolParameterInvalidError(
                "path", path,
                "The path should be an absolute path, starting with `/`.",
            )

        exists = self._file_exists(path)

        if command == "create" and exists:
            raise EditorToolParameterInvalidError(
                "path", path,
                f"File already exists at: {path}. Cannot overwrite with `create`.",
            )
        if command != "create" and not exists:
            raise EditorToolParameterInvalidError(
                "path", path,
                f"The path {path} does not exist.",
            )
        if command not in ("view", "create") and self._is_dir(path):
            raise EditorToolParameterInvalidError(
                "path", path,
                f"{path} is a directory. Only `view` can be used on directories.",
            )

    def _validate_file_size(self, path: str) -> None:
        size = self._get_file_size(path)
        if size > MAX_FILE_SIZE:
            raise ToolError(
                f"File too large ({size / 1024 / 1024:.1f}MB). "
                f"Maximum is {MAX_FILE_SIZE // 1024 // 1024}MB."
            )

    # ── Helpers ───────────────────────────────────────────────────────

    def _make_output(
        self, snippet: str, description: str, start_line: int = 1
    ) -> str:
        snippet = _maybe_truncate(snippet)
        numbered = "\n".join(
            f"{i + start_line:6}\t{line}"
            for i, line in enumerate(snippet.split("\n"))
        )
        return f"Here's the result of running `cat -n` on {description}:\n{numbered}\n"
