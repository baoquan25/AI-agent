# pyright: basic
# type: ignore

"""
Tool registry — creates and registers all tools for OpenHands Agent.

Usage:
    from tools.registry import create_tools

    toolset_name = create_tools(sandbox, execution_log=my_list)
    # => "AgentToolSet"
"""

from openhands.sdk import ToolDefinition
from openhands.sdk.tool import register_tool

from daytona import Sandbox

from tools.code import CodeTool
from tools.editor import FileEditorTool
from tools.read import FileReadTool
from tools.write import FileWriteTool
from tools.list import FileListTool
from tools.delete import FileDeleteTool
from tools.search import FileSearchTool
from tools.folder import CreateFolderTool
from tools.info import FileInfoTool
from tools.grep import GrepTool
from tools.tree import ListTreeTool
from tools.bash import BashTool


# All tool classes — order determines tool listing in agent prompt
ALL_TOOLS = [
    # === Execution ===
    CodeTool,             # Write & run Python code
    BashTool,             # Run any bash command (git, npm, pip, etc.)

    # === File Editing ===
    FileEditorTool,       # str_replace, view, insert, undo
    FileReadTool,         # Read file content
    FileWriteTool,        # Write/create file

    # === File Management ===
    FileListTool,         # List directory (1 level)
    ListTreeTool,         # Recursive directory tree
    FileDeleteTool,       # Delete file/folder
    CreateFolderTool,     # Create directory
    FileInfoTool,         # File metadata (size, permissions)

    # === Search ===
    FileSearchTool,       # Search files by name/glob
    GrepTool,             # Search content inside files
]

# Tools that need extra kwargs beyond just `sandbox`
_TOOLS_WITH_EXTRA_KWARGS = {CodeTool}


def create_tools(sandbox: Sandbox, execution_log: list | None = None) -> str:
    """
    Factory: create and register all tools for OpenHands Agent.

    Args:
        sandbox: Daytona Sandbox instance.
        execution_log: Optional shared list to capture code execution outputs.

    Returns:
        Toolset name ("AgentToolSet") to use in Agent tools list.
    """
    if execution_log is None:
        execution_log = []

    def _make_tools(conv_state) -> list[ToolDefinition]:
        tools = []
        for tool_cls in ALL_TOOLS:
            if tool_cls in _TOOLS_WITH_EXTRA_KWARGS:
                instances = tool_cls.create(
                    conv_state, sandbox=sandbox, execution_log=execution_log
                )
            else:
                instances = tool_cls.create(conv_state, sandbox=sandbox)
            tools.extend(instances)
        return tools

    register_tool("AgentToolSet", _make_tools)
    return "AgentToolSet"
