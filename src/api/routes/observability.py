"""
Observability API Routes (UC-61)

Endpoints for viewing AI cost breakdowns and monitoring metrics.
"""

from fastapi import APIRouter, Depends, status

from src.api.error import ClientError
from src.app.services.unit_of_work import UnitOfWork
from src.app.use_cases.observability import (
    ViewTaskCostUseCase,
    ViewTaskCostResponseDTO,
)
from src.depends import get_unit_of_work, get_current_user

router = APIRouter()


@router.get(
    "/observability/tasks/{task_id}/cost",
    response_model=ViewTaskCostResponseDTO,
    status_code=status.HTTP_200_OK,
)
async def get_task_cost(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """
    Get AI cost breakdown for a task (UC-61).
    Requires authentication.

    Returns total cost and breakdown per pipeline step and agent.
    Cost is aggregated from all AgentRun.actual_cost_credits for the task.
    """
    use_case = ViewTaskCostUseCase(uow=uow, tenant_id=current_user["tenant_id"])
    result = await use_case.execute(task_id)

    if result.is_err():
        if result.error.code == "TASK_NOT_FOUND":
            raise ClientError(result.error, status_code=status.HTTP_404_NOT_FOUND)
        else:
            raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)

    return result.value
