"""
View Task Cost Use Case (UC-61)

User or admin views detailed AI cost breakdown per task and pipeline step.
Cost is aggregated per task with breakdown per step and agent.
"""

from decimal import Decimal
from typing import List

from libs.result import Error, Result, Return
from src.app.services.unit_of_work import UnitOfWork

from .dtos import TaskCostBreakdownDTO, ViewTaskCostResponseDTO


class ViewTaskCostUseCase:
    """
    Use case: View AI Cost per Task (UC-61)

    Retrieves cost breakdown for a task by aggregating actual_cost_credits
    from all AgentRuns associated with the task's pipeline runs.

    Flow:
    1. Verify task exists and belongs to tenant
    2. Get all pipeline runs for the task
    3. For each pipeline run, get all step runs
    4. For each step run, get all agent runs and aggregate costs
    5. Return total cost and breakdown per step/agent
    """

    def __init__(self, uow: UnitOfWork, tenant_id: str):
        self.uow = uow
        self.tenant_id = tenant_id

    async def execute(self, task_id: str) -> Result[ViewTaskCostResponseDTO]:
        """
        Get cost breakdown for a task.

        Args:
            task_id: The task ID to get costs for

        Returns:
            Result[ViewTaskCostResponseDTO]: Cost breakdown with total and per-step details
        """
        async with self.uow:
            # Verify task exists and belongs to tenant
            task = await self.uow.tasks.get_by_id(task_id, self.tenant_id)
            if not task:
                return Return.err(Error(code="TASK_NOT_FOUND", message="Task not found"))

            # Get all pipeline runs for the task
            pipeline_runs = await self.uow.pipeline_runs.get_all_by_task_id(task_id)

            breakdown: List[TaskCostBreakdownDTO] = []
            total_cost = Decimal("0")

            # Aggregate costs from all pipeline runs
            for pipeline_run in pipeline_runs:
                # Get all step runs for this pipeline run
                step_runs = await self.uow.pipeline_steps.get_by_pipeline_run_id(pipeline_run.id)

                for step_run in step_runs:
                    # Get all agent runs for this step run
                    agent_runs = await self.uow.agent_runs.get_by_step_run_id(step_run.id)

                    for agent_run in agent_runs:
                        # Convert credits to Decimal for precision
                        cost = Decimal(str(agent_run.actual_cost_credits))
                        total_cost += cost

                        # Get agent type as string
                        agent_type = (
                            agent_run.agent_type.value
                            if hasattr(agent_run.agent_type, "value")
                            else str(agent_run.agent_type)
                        )

                        breakdown.append(
                            TaskCostBreakdownDTO(
                                step=step_run.step_name,
                                agent=agent_type.lower(),
                                cost=cost,
                            )
                        )

            return Return.ok(
                ViewTaskCostResponseDTO(
                    task_id=task_id,
                    total_cost=total_cost,
                    breakdown=breakdown,
                )
            )
