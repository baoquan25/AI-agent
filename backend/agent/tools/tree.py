# pyright: basic
# type: ignore

"""
ListTreeTool — Recursive directory tree view.

Hiển thị cấu trúc thư mục đệ quy giúp agent hiểu toàn bộ project.
Tương đương lệnh `tree` trên Linux.

Ví dụ output:
  /home/daytona/workspace/
  ├── src/
  │   ├── main.py
  │   ├── config.py
  │   └── utils/
  │       └── helpers.py
  ├── tests/
  │   └── test_main.py
  ├── requirements.txt
  └── README.md

  3 directories, 5 files
"""

from collections.abc import Sequence
from typing import Optional

from pydantic import Field

from openhands.sdk import Action, Observation, TextContent, ImageContent, ToolDefinition
from openhands.sdk.tool import ToolExecutor

from pathlib import Path

from daytona import Sandbox

_DESCRIPTION = (Path(__file__).parent / "tree.txt").read_text(encoding="utf-8").strip()


# ── Action ──────────────────────────────────────────────────────────

class ListTreeAction(Action):
    path: str = Field(
        default="/home/daytona",
        description="Absolute directory path to show tree for",
    )
    depth: Optional[int] = Field(
        default=3,
        description="Maximum depth of directory tree (default: 3). Use -1 for unlimited.",
    )
    include_hidden: bool = Field(
        default=False,
        description="Include hidden files/folders (starting with '.'). Default: False.",
    )
    pattern: Optional[str] = Field(
        default=None,
        description="Optional: only show files matching this glob pattern (e.g. '*.py')",
    )


# ── Observation ─────────────────────────────────────────────────────

class ListTreeObservation(Observation):
    tree: str = ""
    dir_count: int = 0
    file_count: int = 0
    success: bool = True

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        if not self.success:
            return [TextContent(text=f"FAILED: {self.tree}")]
        summary = f"\n\n{self.dir_count} directories, {self.file_count} files"
        return [TextContent(text=f"{self.tree}{summary}")]


# ── Executor ────────────────────────────────────────────────────────

class ListTreeExecutor(ToolExecutor[ListTreeAction, ListTreeObservation]):
    """
    Runs `find` command in sandbox to build a directory tree.
    Uses `tree` if available, falls back to `find` + formatting.
    """

    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox

    def __call__(self, action: ListTreeAction, conversation=None) -> ListTreeObservation:
        try:
            # Try using `tree` command first (cleaner output)
            tree_cmd = self._build_tree_cmd(action)
            result = self.sandbox.process.exec(tree_cmd, timeout=30)
            output = getattr(result, "result", "") or ""
            exit_code = getattr(result, "exit_code", 1) or 1

            if exit_code == 0 and output.strip():
                return self._parse_tree_output(output)

            # Fallback: use `find` command
            find_cmd = self._build_find_cmd(action)
            result = self.sandbox.process.exec(find_cmd, timeout=30)
            output = getattr(result, "result", "") or ""

            return self._format_find_output(output, action.path)

        except Exception as e:
            return ListTreeObservation(tree=str(e), success=False)

    def _build_tree_cmd(self, action: ListTreeAction) -> str:
        safe_path = action.path.replace("'", "'\\''")
        cmd = f"tree '{safe_path}'"

        if action.depth is not None and action.depth >= 0:
            cmd += f" -L {action.depth}"

        if not action.include_hidden:
            cmd += " -I '__pycache__|node_modules|.git|.venv|*.pyc'"

        if action.pattern:
            safe_pattern = action.pattern.replace("'", "'\\''")
            cmd += f" -P '{safe_pattern}'"

        cmd += " --noreport --charset=utf-8 2>/dev/null"
        return cmd

    def _build_find_cmd(self, action: ListTreeAction) -> str:
        safe_path = action.path.replace("'", "'\\''")
        cmd = f"find '{safe_path}'"

        if action.depth is not None and action.depth >= 0:
            cmd += f" -maxdepth {action.depth}"

        if not action.include_hidden:
            cmd += " -not -path '*/\\.*' -not -path '*/__pycache__/*' -not -path '*/node_modules/*' -not -path '*/.venv/*'"

        if action.pattern:
            safe_pattern = action.pattern.replace("'", "'\\''")
            cmd += f" -name '{safe_pattern}'"

        cmd += " 2>/dev/null | sort | head -500"
        return cmd

    def _parse_tree_output(self, output: str) -> ListTreeObservation:
        """Parse tree command output and count dirs/files."""
        lines = output.strip().splitlines()
        dir_count = 0
        file_count = 0
        for line in lines:
            # tree marks directories with trailing /
            stripped = line.rstrip()
            # Extract the actual name part (after tree drawing characters)
            name_part = stripped.lstrip("│├└─ \t")
            if name_part.endswith("/"):
                dir_count += 1
            elif name_part:
                file_count += 1

        return ListTreeObservation(
            tree=output.strip(),
            dir_count=dir_count,
            file_count=file_count,
            success=True,
        )

    def _format_find_output(self, output: str, root: str) -> ListTreeObservation:
        """Format `find` output into a simple tree-like display."""
        if not output.strip():
            return ListTreeObservation(
                tree=f"{root}/\n  (empty)",
                dir_count=0,
                file_count=0,
                success=True,
            )

        lines = output.strip().splitlines()
        dir_count = 0
        file_count = 0
        formatted = []

        for line in lines:
            path = line.strip()
            if path == root or path == root.rstrip("/"):
                continue

            # Make relative to root
            rel = path[len(root):].lstrip("/")
            depth = rel.count("/")
            indent = "  " * depth
            name = rel.rsplit("/", 1)[-1] if "/" in rel else rel

            if path.endswith("/") or not name or "." not in name.split("/")[-1]:
                # Try to detect directories
                # We'll check via a heuristic: if it appears as a prefix of other entries
                formatted.append(f"{indent}{name}/")
                dir_count += 1
            else:
                formatted.append(f"{indent}{name}")
                file_count += 1

        tree_output = f"{root}/\n" + "\n".join(formatted)

        return ListTreeObservation(
            tree=tree_output,
            dir_count=dir_count,
            file_count=file_count,
            success=True,
        )


class ListTreeTool(ToolDefinition[ListTreeAction, ListTreeObservation]):
    """Show recursive directory tree in sandbox."""
    name = "daytona_list_tree"

    @classmethod
    def create(cls, conv_state, *, sandbox: Sandbox) -> Sequence[ToolDefinition]:
        executor = ListTreeExecutor(sandbox)
        return [cls(
            description=_DESCRIPTION,
            action_type=ListTreeAction,
            observation_type=ListTreeObservation,
            executor=executor,
        )]
