from typing import Optional
from libs.result import Result, Error, Return
from src.app.services.unit_of_work import UnitOfWork
from .dtos import PipelineTimelineResponseDTO, PipelineStepDTO


class GetPipelineTimelineUseCase:
    """
    Use case: Get Pipeline Timeline (UC-15 / Story 3.2)

    Retrieves the timeline of a pipeline run showing all steps with their status,
    timestamps, and error messages.
    """

    def __init__(self, uow: UnitOfWork, tenant_id: str):
        self.uow = uow
        self.tenant_id = tenant_id

    async def execute(
        self, task_id: str, run_id: Optional[str] = None
    ) -> Result[PipelineTimelineResponseDTO]:
        """
        Get pipeline timeline for a task

        Args:
            task_id: The task ID
            run_id: Optional specific pipeline run ID. If not provided, returns most recent run.

        Returns:
            Result[PipelineTimelineResponseDTO]: Pipeline timeline with all steps
        """
        async with self.uow:
            # Verify task exists and belongs to tenant (repository filters by tenant_id)
            task = await self.uow.tasks.get_by_id(task_id, self.tenant_id)
            if not task:
                return Return.err(Error(code="TASK_NOT_FOUND", message="Task not found"))

            # Get pipeline run (specific or most recent)
            if run_id:
                pipeline_run = await self.uow.pipeline_runs.get_by_id(run_id)
                if not pipeline_run:
                    return Return.err(
                        Error(code="PIPELINE_RUN_NOT_FOUND", message="Pipeline run not found")
                    )
                if pipeline_run.task_id != task_id:
                    return Return.err(
                        Error(
                            code="INVALID_PIPELINE_RUN",
                            message="Pipeline run does not belong to this task",
                        )
                    )
            else:
                pipeline_run = await self.uow.pipeline_runs.get_by_task_id(task_id)
                if not pipeline_run:
                    return Return.err(
                        Error(code="NO_PIPELINE_RUN", message="No pipeline run found for this task")
                    )

            # Get all steps for this pipeline run
            steps = await self.uow.pipeline_steps.get_by_pipeline_run_id(pipeline_run.id)

            # Convert to DTOs
            step_dtos = [
                PipelineStepDTO(
                    id=step.id,
                    step_number=step.step_number,
                    step_name=step.step_name,
                    status=step.status.value if hasattr(step.status, "value") else step.status,
                    started_at=step.started_at,
                    completed_at=step.completed_at,
                    output=getattr(step, "output", None),
                    error_message=getattr(step, "error_message", None),
                )
                for step in steps
            ]

            response = PipelineTimelineResponseDTO(
                id=pipeline_run.id,
                task_id=pipeline_run.task_id,
                status=(
                    pipeline_run.status.value
                    if hasattr(pipeline_run.status, "value")
                    else pipeline_run.status
                ),
                started_at=pipeline_run.started_at,
                completed_at=pipeline_run.completed_at,
                error_message=getattr(pipeline_run, "error_message", None),
                steps=step_dtos,
            )

            return Return.ok(response)
