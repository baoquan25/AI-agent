from openhands.sdk import ToolDefinition
from openhands.sdk.tool import register_tool

from daytona import Sandbox

from tools.run import RunFileTool
from tools.editor import DaytonaFileEditorTool as FileEditorTool
from tools.apply_patch import ApplyPatchTool
from tools.grep import GrepTool
from tools.glob import GlobTool
from tools.terminal import DaytonaTerminalTool as TerminalTool
from tools.browser_use import BrowserToolSet

ALL_TOOLS = [
    # === Execution ===
    RunFileTool,          # Run existing file via /run API (same as Run button)
    TerminalTool,         # Execute bash commands in sandbox terminal

    # === File Editing ===
    FileEditorTool,       # view, create, str_replace, insert, undo_edit
    ApplyPatchTool,       # Multi-file patch (add, update, delete, move)

    # === Search ===
    GrepTool,             # Search content inside files
    GlobTool,             # Find files by glob pattern (e.g. **/*.py)

    # === Browser ===
    BrowserToolSet,       # Web automation (navigate, click, type, tabs, storage, recording)
]


def create_tools(sandbox: Sandbox, user_id: str = "default_user",
                  execution_log: list | None = None,
                  file_edits: list | None = None) -> str:
    if execution_log is None:
        execution_log = []
    if file_edits is None:
        file_edits = []

    def _make_tools(conv_state) -> list[ToolDefinition]:
        tools = []
        for tool_cls in ALL_TOOLS:
            if tool_cls is RunFileTool:
                instances = tool_cls.create(conv_state, sandbox=sandbox, execution_log=execution_log)
            elif tool_cls in (FileEditorTool, ApplyPatchTool):
                instances = tool_cls.create(conv_state, sandbox=sandbox, file_edits=file_edits)
            elif tool_cls is BrowserToolSet:
                instances = tool_cls.create(conv_state)
            else:
                instances = tool_cls.create(conv_state, sandbox=sandbox)
            tools.extend(instances)
        return tools

    toolset_name = f"AgentToolSet_{user_id}"
    register_tool(toolset_name, _make_tools)
    return toolset_name
