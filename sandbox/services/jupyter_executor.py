# pyright: basic
# type: ignore

"""
JupyterKernelExecutor — Execute code via Jupyter kernel in sandbox.

Moved from services/output_executor.py (same logic, new location).
"""

import json
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


class JupyterKernelExecutor:
    """
    Execute code using a Jupyter Kernel (without a Jupyter Server).

    - Uploads user code + wrapper script to sandbox
    - Wrapper starts kernel via jupyter_client, executes code
    - Captures: stdout, stderr, display_data, execute_result, error traceback
    """

    def __init__(self, sandbox: Any) -> None:
        self.sandbox: Any = sandbox
        self.session_id: str = str(uuid.uuid4())
        self.initialized: bool = False

    def initialize(self):
        if self.initialized:
            return
        self.initialized = True

    def execute(self, code: str, timeout: int = 30) -> dict[str, Any]:
        """
        Returns:
            {
                "success": bool,
                "stdout": str,
                "stderr": str,
                "outputs": List[{"type": mime, "data": ..., "library": optional}],
                "error": Optional[str]
            }
        """
        try:
            self.initialize()
            return self._execute_via_ipython(code=code, timeout=timeout)
        except Exception as e:
            logger.exception("Execute error")
            return {
                "success": False,
                "stdout": "",
                "stderr": "",
                "outputs": [],
                "error": str(e),
            }

    def _execute_via_ipython(self, code: str, timeout: int) -> dict[str, Any]:
        code_path = f"/tmp/ipython_user_code_{self.session_id}.py"
        wrapper_path = f"/tmp/ipython_wrapper_{self.session_id}.py"

        self.sandbox.fs.upload_file(code.encode("utf-8"), code_path)
        self.sandbox.fs.upload_file(
            self._build_wrapper_script(code_path, timeout=timeout).encode("utf-8"),
            wrapper_path,
        )

        try:
            resp = self.sandbox.process.exec(
                f"python3 {wrapper_path}",
                timeout=timeout + 30,
            )
            output = getattr(resp, "result", "") or ""
            exit_code = getattr(resp, "exit_code", 0) or 0

            if "__IPY_RESULT_START__" not in output:
                err = f"Wrapper failed (exit_code={exit_code}). Raw output:\n{output}"
                logger.error(err[:2000])
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": output,
                    "outputs": [],
                    "error": err,
                }

            return self._parse_result(output)

        except Exception as e:
            logger.exception("Process exec error")
            return {
                "success": False,
                "stdout": "",
                "stderr": "",
                "outputs": [],
                "error": f"Process execution error: {str(e)}",
            }

    def _parse_result(self, output: str) -> dict[str, Any]:
        start = output.find("__IPY_RESULT_START__")
        end = output.find("__IPY_RESULT_END__")

        if start == -1 or end == -1 or end <= start:
            return {
                "success": False,
                "stdout": output,
                "stderr": "",
                "outputs": [],
                "error": "No result markers found",
            }

        json_str = output[start + len("__IPY_RESULT_START__") : end].strip()
        try:
            result = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return {
                "success": False,
                "stdout": output,
                "stderr": "",
                "outputs": [],
                "error": f"JSON parse error: {e}",
            }

        if result.get("error"):
            logger.error(f"User code error:\n{result['error'][:2000]}")

        return result

    def _build_wrapper_script(self, code_path: str, timeout: int) -> str:
        return f"""
import sys
import json
import traceback
import time

def _run_kernel():
    try:
        import ipykernel  # noqa: F401
        from jupyter_client import KernelManager
    except Exception:
        return {{
            "success": False,
            "stdout": "",
            "stderr": "",
            "outputs": [],
            "error": "Missing dependency: ipykernel and jupyter_client",
        }}

    stdout_chunks = []
    stderr_chunks = []
    outputs = []
    success = True
    error = None

    km = KernelManager(kernel_name="python3")
    kc = None
    try:
        km.start_kernel()
        kc = km.client()
        kc.start_channels()
        kc.wait_for_ready(timeout=10)

        with open("{code_path}", "r", encoding="utf-8") as f:
            user_code = f.read()

        msg_id = kc.execute(user_code, allow_stdin=False, stop_on_error=False)

        deadline = time.time() + {timeout}
        while True:
            if time.time() > deadline:
                success = False
                error = "Execution timed out"
                break

            try:
                msg = kc.get_iopub_msg(timeout=1)
            except Exception:
                continue

            msg_type = msg.get("msg_type")
            content = msg.get("content", {{}})

            if msg_type == "stream":
                name = content.get("name")
                text = content.get("text", "")
                if name == "stdout":
                    stdout_chunks.append(text)
                elif name == "stderr":
                    stderr_chunks.append(text)
            elif msg_type in ("display_data", "execute_result"):
                data = content.get("data", {{}})
                for mime, value in data.items():
                    outputs.append({{"type": mime, "data": value}})
            elif msg_type == "error":
                success = False
                tb = content.get("traceback", [])
                error = "\\n".join(tb) if tb else content.get("evalue")
            elif msg_type == "status":
                if content.get("execution_state") == "idle":
                    break

        return {{
            "success": success,
            "stdout": "".join(stdout_chunks),
            "stderr": "".join(stderr_chunks),
            "outputs": outputs,
            "error": error,
        }}
    except Exception:
        return {{
            "success": False,
            "stdout": "",
            "stderr": "",
            "outputs": [],
            "error": traceback.format_exc(),
        }}
    finally:
        if kc is not None:
            try:
                kc.stop_channels()
            except Exception:
                pass
        try:
            km.shutdown_kernel(now=True)
        except Exception:
            pass

result = _run_kernel()

print("__IPY_RESULT_START__")
print(json.dumps(result, ensure_ascii=False))
print("__IPY_RESULT_END__")
"""
