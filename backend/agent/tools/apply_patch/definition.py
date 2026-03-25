# pyright: basic
# type: ignore

import posixpath
from collections.abc import Sequence

from pydantic import Field

from openhands.sdk import Action, Observation, TextContent, ImageContent, ToolDefinition
from openhands.sdk.tool import ToolExecutor

from daytona import Sandbox

from .core import Commit, DiffError, process_patch
from dependencies import WORKSPACE
from tools.notify import notify_file_change


_DESCRIPTION = """Use the `apply_patch` tool to edit files. Your patch language is a stripped‑down, file‑oriented diff format designed to be easy to parse and safe to apply. You can think of it as a high‑level envelope:

Required format:
- Start with `*** Begin Patch`
- End with `*** End Patch`
- Include one or more operations:
  - `*** Update File: <path>`
  - `*** Add File: <path>`
  - `*** Delete File: <path>`
- Optional after `*** Update File:`: `*** Move to: <new_path>`

Line prefixes in update hunks:
- ` ` context
- `-` delete
- `+` add
- `@@ <line>` anchor
- `*** End of File` for EOF anchoring

Path rules:
- Must stay inside workspace
- Preferred: `workspace/...` or `/home/daytona/workspace/...`
- `/workspace/...` is normalized to `/home/daytona/workspace/...`
- No `..` traversal and no host paths like `/home/ducminh/...`

Do not wrap patch text in Markdown code fences.

Example:
*** Begin Patch
*** Add File: hello.txt
+Hello world
*** Update File: src/app.py
*** Move to: src/main.py
@@ def greet():
-print("Hi")
+print("Hello, world!")
*** Delete File: obsolete.txt
*** End Patch

Use `apply_patch` for multi-file or multi-hunk edits.
Use `str_replace` (file_editor) for one targeted single-file edit.
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

    def _strip_workspace_prefix(self, path: str) -> tuple[str, bool]:
        value = path.strip()
        if not value:
            return "", False

        value_no_trailing = value.rstrip("/") or "/"
        workspace_aliases = (
            WORKSPACE.rstrip("/") or "/",
            "/home/daytona/workspace",
            "/workspace",
            "workspace",
        )

        if value_no_trailing in workspace_aliases:
            return "", True

        for alias in workspace_aliases:
            prefix = f"{alias}/"
            if value.startswith(prefix):
                return value[len(prefix) :].lstrip("/"), True

        return value, False

    def _normalize_workspace_path(self, path: str) -> str:
        raw_path = (path or "").strip()
        if not raw_path:
            raise DiffError("Path is required")

        rel_path, is_workspace_anchored = self._strip_workspace_prefix(raw_path)

        if rel_path.startswith("/"):
            raise DiffError(
                f"Path must be inside workspace ({WORKSPACE}): {raw_path}"
            )

        normalized_rel = posixpath.normpath(rel_path).lstrip("/")
        if normalized_rel in ("", "."):
            if is_workspace_anchored:
                return WORKSPACE
            raise DiffError(f"Path must point inside workspace: {raw_path}")
        if normalized_rel == ".." or normalized_rel.startswith("../"):
            raise DiffError(f"Path escapes workspace: {raw_path}")

        return f"{WORKSPACE}/{normalized_rel}"

    def _normalize_patch_paths(self, patch_text: str) -> str:
        path_prefixes = (
            "*** Update File: ",
            "*** Delete File: ",
            "*** Add File: ",
            "*** Move to: ",
        )
        out_lines: list[str] = []
        for line in patch_text.split("\n"):
            rewritten = False
            for prefix in path_prefixes:
                if line.startswith(prefix):
                    original_path = line[len(prefix) :]
                    normalized_path = self._normalize_workspace_path(original_path)
                    out_lines.append(f"{prefix}{normalized_path}")
                    rewritten = True
                    break
            if not rewritten:
                out_lines.append(line)
        return "\n".join(out_lines)

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
            action = "create" if change.type == ActionType.ADD else change.type.value
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
            normalized_patch = self._normalize_patch_paths(action.patch)
            msg, fuzz, commit = process_patch(
                normalized_patch,
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

    @classmethod
    def create(cls, conv_state, *, sandbox: Sandbox | None = None, file_edits: list | None = None) -> Sequence[ToolDefinition]:
        if sandbox is None:
            sandbox = conv_state.agent_state.get("sandbox")
        if not sandbox:
            raise ValueError("sandbox not found in conv_state.agent_state")
        if file_edits is None:
            file_edits = conv_state.agent_state.get("file_edits")
        executor = ApplyPatchExecutor(sandbox, file_edits=file_edits)
        return [cls(
            description=_DESCRIPTION,
            action_type=ApplyPatchAction,
            observation_type=ApplyPatchObservation,
            executor=executor,
        )]
