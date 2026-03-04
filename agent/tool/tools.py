from langchain_core.tools import tool

# SDK path: Daytona API dùng "workspace" cho thư mục workspace (không dùng /home/daytona/workspace)
WORKSPACE_ROOT = "workspace"


def _sdk_path(relative: str = "") -> str:
    p = (relative or "").strip().strip("/")
    return f"{WORKSPACE_ROOT}/{p}" if p else WORKSPACE_ROOT

def get_tools(sandbox):
    if sandbox is None:
        raise RuntimeError(
            "Sandbox is not available for this user. "
        )

    @tool
    def read_file(path: str) -> str:
        """Read a file from the sandbox workspace.
        Use relative path inside workspace, e.g. 'src/main.py' or '' for workspace root."""
        sdk_path = _sdk_path(path)
        try:
            return sandbox.fs.read_file(sdk_path)
        except Exception as e:
            return f"Error reading {sdk_path}: {e}"

    @tool
    def list_files(path: str = "") -> str:
        """List files and directories in the sandbox workspace.
        Use relative path, e.g. 'src' or '' for workspace root."""
        sdk_path = _sdk_path(path)
        try:
            entries = sandbox.fs.list_files(sdk_path)
            lines = [
                (f"{getattr(f, 'name', str(f))}/" if getattr(f, "is_dir", False) else getattr(f, "name", str(f)))
                for f in entries
            ]
            return "\n".join(lines) if lines else "(empty directory)"
        except Exception as e:
            return f"Error listing {sdk_path}: {e}"

    @tool
    def write_file(path: str, content: str) -> str:
        """Write content to a file in the sandbox workspace. Creates the file if it doesn't exist.
        Use relative path, e.g. 'src/main.py'."""
        sdk_path = _sdk_path(path)
        try:
            sandbox.fs.upload_file(content.encode("utf-8"), sdk_path)
            return f"Written to {sdk_path}"
        except Exception as e:
            return f"Error writing {sdk_path}: {e}"

    @tool
    def run_command(command: str) -> str:
        """Run a shell command inside the Daytona sandbox."""
        try:
            result = sandbox.process.exec(command)
            output = (result.output or "").strip()
            return f"Exit code: {result.exit_code}\n{output}" if output else f"Exit code: {result.exit_code}"
        except Exception as e:
            return f"Error executing command: {e}"

    return [read_file, list_files, write_file, run_command]