from openhands.sdk.tool import Tool, register_tool

from tools.run.definition import RunFileTool
from tools.terminal.definition import TerminalTool
from tools.editor.definition import FileEditorTool
from tools.apply_patch.definition import ApplyPatchTool
from tools.grep.definition import GrepTool
from tools.glob.definition import GlobTool
from tools.browser_use.definition import BrowserToolSet

_registered = False

# Tool name → class mapping (registered once at startup)
_TOOL_CLASSES = {
    "RunFileTool":    RunFileTool,
    "TerminalTool":   TerminalTool,
    "FileEditorTool": FileEditorTool,
    "ApplyPatchTool": ApplyPatchTool,
    "GrepTool":       GrepTool,
    "GlobTool":       GlobTool,
    "BrowserToolSet": BrowserToolSet,
}

TOOL_NAMES = list(_TOOL_CLASSES.keys())


def register_all_tools() -> None:
    global _registered
    if _registered:
        return
    for name, cls in _TOOL_CLASSES.items():
        register_tool(name, cls)
    _registered = True


def get_tool_references() -> list[Tool]:
    return [Tool(name=name) for name in TOOL_NAMES]
