from __future__ import annotations

import logging
from typing import Any

from services.jupyter_executor import JupyterKernelExecutor

logger = logging.getLogger("daytona-api")


class ExecutionService:

    def run_code(self, sandbox, code: str, *, use_jupyter: bool = True, timeout: int = 30) -> dict[str, Any]:
        if use_jupyter:
            return self._run_jupyter(sandbox, code, timeout)
        return self._run_direct(sandbox, code, timeout)

    def _run_jupyter(self, sandbox, code: str, timeout: int) -> dict[str, Any]:
        """Run via Jupyter kernel, fallback to direct if IPython missing."""
        executor = JupyterKernelExecutor(sandbox)
        result = executor.execute(code, timeout=timeout)

        error_text = result.get("error", "") or ""

        # Fallback if sandbox lacks IPython
        if "No module named 'IPython'" in error_text:
            direct = self._run_direct(sandbox, code, timeout)
            direct["output"] += "\n\nNote: Executed without IPython"
            return direct

        stdout_text = result.get("stdout", "") or ""
        stderr_text = result.get("stderr", "") or ""

        # Build outputs list
        outputs = []
        for item in result.get("outputs", []) or []:
            if isinstance(item, dict) and "type" in item and "data" in item:
                outputs.append({
                    "type": item["type"],
                    "data": item["data"],
                    "library": item.get("library"),
                })

        output_text = stdout_text
        if stderr_text.strip():
            output_text += f"\n\nSTDERR:\n{stderr_text}"
        if error_text:
            output_text += f"\n\nERROR:\n{error_text}"
            return {"output": output_text, "exit_code": 1, "success": False, "outputs": outputs}

        return {
            "output": output_text,
            "exit_code": 0 if result.get("success", True) else 1,
            "success": result.get("success", True),
            "outputs": outputs,
        }

    @staticmethod
    def _run_direct(sandbox, code: str, timeout: int) -> dict[str, Any]:
        """Run code directly via sandbox.process.code_run."""
        resp = sandbox.process.code_run(code, timeout=timeout)
        out = getattr(resp, "result", "") or ""
        exit_code = getattr(resp, "exit_code", 0) or 0
        return {
            "output": out,
            "exit_code": exit_code,
            "success": exit_code == 0,
            "outputs": [],
        }
