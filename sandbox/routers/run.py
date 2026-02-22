import logging

from fastapi import APIRouter, Depends, Header

from dependencies import get_sandbox, get_workspace_manager
from models.execution import RunCodeRequest, RunCodeResponse, OutputItem
from services.execution_service import ExecutionService

logger = logging.getLogger("daytona-api")

router = APIRouter(tags=["Code Execution"])

_execution_service = ExecutionService()


@router.post("/run", response_model=RunCodeResponse)
async def run_code(
    req: RunCodeRequest,
    sandbox_and_id=Depends(get_sandbox),
    wm=Depends(get_workspace_manager),
):
    sandbox, sandbox_id = sandbox_and_id
    logger.info(f"run sandbox={sandbox_id}")

    code_to_run = req.code
    if req.file_path:
        code_to_run = wm.wrap_code(req.code, req.file_path)

    result = _execution_service.run_code(
        sandbox, code_to_run, use_jupyter=req.use_jupyter, timeout=req.timeout,
    )

    outputs = [
        OutputItem(type=o["type"], data=o["data"], library=o.get("library"))
        for o in result.get("outputs", [])
    ]

    return RunCodeResponse(
        output=result["output"],
        exit_code=result["exit_code"],
        sandbox_id=sandbox_id,
        success=result["success"],
        outputs=outputs,
    )
