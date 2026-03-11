# pyright: basic
# type: ignore

import posixpath
from collections.abc import Sequence

from pydantic import Field

from openhands.sdk import Action, Observation, TextContent, ImageContent, ToolDefinition
from openhands.sdk.tool import ToolExecutor

from daytona import Sandbox

from .core import Commit, DiffError, process_patch
from tools.notify import notify_file_change


_DESCRIPTION = """Apply a patch to modify multiple files in a single operation.

The patch must use this exact format:

*** Begin Patch
*** Update File: <path>
@@ <context line from original file>
 <unchanged line (space prefix)>
-<line to remove>
+<line to add>
 <unchanged line>
*** End Patch

Rules:
- Lines starting with " " (space) are context/unchanged lines
- Lines starting with "+" are added lines
- Lines starting with "-" are removed lines
- Use "@@ <line>" to anchor the context position in the original file
- Use "*** Add File: <path>" followed by lines starting with "+" to create a new file
- Use "*** Delete File: <path>" to remove a file
- Use "*** Move to: <new_path>" after "*** Update File:" to rename/move a file
- Use "*** End of File" to anchor changes at the end of a file
- Multiple file operations can be included in a single patch

Example — update one file and create another:

*** Begin Patch
*** Update File: src/main.py
@@ def hello():
-    return "old"
+    return "new"
*** Add File: src/utils.py
+def helper():
+    return True
*** End Patch

When to use apply_patch vs str_replace:
- Use apply_patch when modifying MULTIPLE files at once or making MULTIPLE changes to the same file
- Use str_replace (file_editor) for single, targeted edits in one file
"""


class ApplyPatchAction(Action):
    patch: str = Field(
        description="Patch content in '*** Begin Patch' ... '*** End Patch' format."
    )


class ApplyPatchObservation(Observation):
    message: str = ""
    fuzz: int = 0
    files_changed: int = 0
    commit: Commit | None = None

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        if self.files_changed == 0 and self.message:
            return [TextContent(text=f"PATCH FAILED: {self.message}")]
        fuzz_note = f" (fuzz: {self.fuzz})" if self.fuzz > 0 else ""
        return [TextContent(
            text=f"Patch applied successfully. {self.files_changed} file(s) changed.{fuzz_note}"
        )]


class ApplyPatchExecutor(ToolExecutor[ApplyPatchAction, ApplyPatchObservation]):

    def __init__(self, sandbox: Sandbox, file_edits: list | None = None):
        self.sandbox = sandbox
        self._file_edits = file_edits

    def _read_file(self, path: str) -> str:
        content_bytes = self.sandbox.fs.download_file(path)
        if isinstance(content_bytes, bytes):
            return content_bytes.decode("utf-8", errors="replace")
        return str(content_bytes)

    def _ensure_parents(self, path: str) -> None:
        parent = posixpath.dirname(path)
        if parent and parent != "/":
            try:
                self.sandbox.fs.create_folder(parent, "755")
            except Exception:
                pass

    def _write_file(self, path: str, content: str) -> None:
        try:
            self.sandbox.fs.upload_file(content.encode("utf-8"), path)
        except Exception:
            self._ensure_parents(path)
            self.sandbox.fs.upload_file(content.encode("utf-8"), path)

    def _remove_file(self, path: str) -> None:
        self.sandbox.fs.delete_file(path)

    def _track_edits_from_commit(self, commit: Commit) -> None:
        if self._file_edits is None:
            return
        from .core import ActionType
        for path, change in commit.changes.items():
            action = change.type.value
            existing = next((e for e in self._file_edits if e["path"] == path), None)
            if existing:
                existing["new_content"] = change.new_content
                existing["action"] = action
            else:
                self._file_edits.append({
                    "path": path,
                    "action": action,
                    "old_content": change.old_content,
                    "new_content": change.new_content,
                })

    def _notify_commit(self, commit: Commit) -> None:
        from .core import ActionType
        _type_to_change = {
            ActionType.ADD: "added",
            ActionType.UPDATE: "updated",
            ActionType.DELETE: "deleted",
        }
        for path, change in commit.changes.items():
            notify_file_change(path, _type_to_change.get(change.type, "updated"))

    def __call__(self, action: ApplyPatchAction, conversation=None) -> ApplyPatchObservation:
        try:
            msg, fuzz, commit = process_patch(
                action.patch,
                open_fn=self._read_file,
                write_fn=self._write_file,
                remove_fn=self._remove_file,
            )
            self._track_edits_from_commit(commit)
            self._notify_commit(commit)
            return ApplyPatchObservation(
                message=msg,
                fuzz=fuzz,
                files_changed=len(commit.changes),
                commit=commit,
            )
        except DiffError as e:
            return ApplyPatchObservation(message=str(e))
        except Exception as e:
            return ApplyPatchObservation(message=str(e))


class ApplyPatchTool(ToolDefinition[ApplyPatchAction, ApplyPatchObservation]):
    """Apply unified text patches to files in the sandbox."""
    name = "daytona_apply_patch"

    @classmethod
    def create(cls, conv_state, *, sandbox: Sandbox, file_edits: list | None = None) -> Sequence[ToolDefinition]:
        executor = ApplyPatchExecutor(sandbox, file_edits=file_edits)
        return [cls(
            description=_DESCRIPTION,
            action_type=ApplyPatchAction,
            observation_type=ApplyPatchObservation,
            executor=executor,
        )]
