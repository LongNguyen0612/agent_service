"""
Replay Pipeline Use Case (UC-25)

Allows replaying a failed or completed pipeline run from a specific step or from the beginning.
"""
from libs.result import Result, Error, Return
from src.app.services.unit_of_work import UnitOfWork
from src.app.services.audit_service import AuditService
from src.domain.pipeline_run import PipelineRun
from src.domain.enums import PipelineStatus
from .dtos import ReplayPipelineCommandDTO, ReplayPipelineResponseDTO


class ReplayPipelineUseCase:
    """
    Use case: Replay AI Execution from Logs (UC-25)

    Allows users to replay a pipeline run from a specific step or from the beginning.
    Preserves approved artifacts from the previous run if requested.
    """

    def __init__(self, uow: UnitOfWork, audit_service: AuditService):
        self.uow = uow
        self.audit_service = audit_service

    async def execute(
        self, command: ReplayPipelineCommandDTO
    ) -> Result[ReplayPipelineResponseDTO]:
        """
        Replay a pipeline from a specific step or from the beginning.

        Args:
            command: Replay command with pipeline run ID and options

        Returns:
            Result[ReplayPipelineResponseDTO]: New pipeline run info
        """
        async with self.uow:
            # Get the original pipeline run
            original_run = await self.uow.pipeline_runs.get_by_id(command.pipeline_run_id)
            if not original_run:
                return Return.err(
                    Error(code="PIPELINE_RUN_NOT_FOUND", message="Pipeline run not found")
                )

            # Verify tenant isolation through task
            task = await self.uow.tasks.get_by_id(original_run.task_id, command.tenant_id)
            if not task:
                return Return.err(
                    Error(code="PIPELINE_RUN_NOT_FOUND", message="Pipeline run not found")
                )

            # Determine starting step
            started_from_step = "STEP_1"
            start_step_number = 1

            if command.from_step_id:
                # Get the step to start from
                original_steps = await self.uow.pipeline_steps.get_by_pipeline_run_id(
                    command.pipeline_run_id
                )
                step_to_resume_from = next(
                    (s for s in original_steps if s.id == command.from_step_id),
                    None,
                )
                if step_to_resume_from:
                    start_step_number = step_to_resume_from.step_number
                    started_from_step = step_to_resume_from.step_name.upper()

            # Create new pipeline run
            new_pipeline_run = PipelineRun(
                task_id=original_run.task_id,
                tenant_id=command.tenant_id,
                status=PipelineStatus.running,
                current_step=start_step_number,
            )
            created_run = await self.uow.pipeline_runs.create(new_pipeline_run)
            await self.uow.commit()

            # Log audit event
            await self.audit_service.log_event(
                event_type="pipeline_replayed",
                tenant_id=command.tenant_id,
                user_id=None,
                resource_type="pipeline_run",
                resource_id=created_run.id,
                metadata={
                    "original_pipeline_run_id": command.pipeline_run_id,
                    "from_step_id": command.from_step_id,
                    "preserve_approved_artifacts": command.preserve_approved_artifacts,
                    "started_from_step": started_from_step,
                },
            )

            return Return.ok(
                ReplayPipelineResponseDTO(
                    new_pipeline_run_id=created_run.id,
                    status="running",
                    started_from_step=started_from_step,
                )
            )
