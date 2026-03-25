from openhands.sdk.tool import Tool, register_tool

from tools.run.definition import RunFileTool
from tools.terminal.definition import TerminalTool
from tools.editor.definition import FileEditorTool
from tools.apply_patch.definition import ApplyPatchTool
from tools.grep.definition import GrepTool
from tools.glob.definition import GlobTool
from tools.browser_use.definition import BrowserToolSet

_REGISTERED = False

def register_all_tools():
    global _REGISTERED
    if _REGISTERED:
        return
    register_tool("FileEditorTool", FileEditorTool)
    register_tool("RunFileTool", RunFileTool)
    register_tool("TerminalTool", TerminalTool)
    register_tool("ApplyPatchTool", ApplyPatchTool)
    register_tool("GrepTool", GrepTool)
    register_tool("GlobTool", GlobTool)
    register_tool("BrowserToolSet", BrowserToolSet)
    _REGISTERED = True

def get_tool_references():
    return [
        Tool(name="FileEditorTool"),
        Tool(name="RunFileTool"),
        Tool(name="TerminalTool"),
        Tool(name="ApplyPatchTool"),
        Tool(name="GrepTool"),
        Tool(name="GlobTool"),
        Tool(name="BrowserToolSet"),
    ]
