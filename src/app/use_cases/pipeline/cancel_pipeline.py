"""Cancel Pipeline Use Case - Story 2.6

Implements pipeline cancellation with preservation of completed work.
"""
import logging
from datetime import datetime
from libs.result import Result, Return, Error
from src.domain.enums import PipelineStatus, StepStatus
from src.app.repositories.pipeline_run_repository import IPipelineRunRepository
from src.app.repositories.pipeline_step_repository import IPipelineStepRunRepository
from src.app.services.audit_service import AuditService
from .dtos import CancelPipelineCommandDTO, CancellationResultDTO

logger = logging.getLogger(__name__)


class CancelPipeline:
    """
    Use case for cancelling a running pipeline - AC-2.6.1

    Implements:
    - AC-2.6.1: Cancel running pipeline
    - AC-2.6.2: Cannot cancel completed pipeline
    - AC-2.6.3: Preserve completed work
    - AC-2.6.4: Stop in-progress step
    - AC-2.6.5: Audit trail
    """

    def __init__(
        self,
        pipeline_run_repository: IPipelineRunRepository,
        step_run_repository: IPipelineStepRunRepository,
        audit_service: AuditService = None,
    ):
        """
        Initialize CancelPipeline use case.

        Args:
            pipeline_run_repository: Repository for pipeline runs
            step_run_repository: Repository for pipeline step runs
            audit_service: Service for audit logging (optional)
        """
        self.pipeline_run_repository = pipeline_run_repository
        self.step_run_repository = step_run_repository
        self.audit_service = audit_service

    async def execute(
        self, command: CancelPipelineCommandDTO
    ) -> Result[CancellationResultDTO]:
        """
        Execute pipeline cancellation.

        Flow:
        1. Get pipeline run and verify ownership (tenant_id)
        2. Validate that pipeline is cancellable
        3. Get all steps to count completed vs cancelled
        4. Update pipeline status to cancelled
        5. Mark running steps as cancelled
        6. Emit audit event
        7. Return result

        Args:
            command: Command with pipeline_run_id, tenant_id, user_id, reason

        Returns:
            Result[CancellationResultDTO]: Cancellation result with stats
        """
        # Step 1: Get pipeline run
        pipeline = await self.pipeline_run_repository.get_by_id(command.pipeline_run_id)

        if not pipeline:
            return Return.err(
                Error(
                    code="PIPELINE_NOT_FOUND",
                    message=f"Pipeline run {command.pipeline_run_id} not found",
                )
            )

        # Verify tenant ownership - AC-2.6.1
        if pipeline.tenant_id != command.tenant_id:
            return Return.err(
                Error(
                    code="UNAUTHORIZED",
                    message="Not authorized to cancel this pipeline",
                )
            )

        # Step 2: Validate cancellable status - AC-2.6.2
        if pipeline.status in [PipelineStatus.completed, PipelineStatus.cancelled]:
            return Return.err(
                Error(
                    code="CANNOT_CANCEL_COMPLETED",
                    message=f"Cannot cancel pipeline with status {pipeline.status.value}",
                )
            )

        # Store previous status for response
        previous_status = pipeline.status.value

        # Step 3: Get all steps and count completed - AC-2.6.3
        steps = await self.step_run_repository.get_by_pipeline_run_id(pipeline.id)
        completed_count = len([s for s in steps if s.status == StepStatus.completed])

        # Step 4: Mark running steps as cancelled - AC-2.6.4
        for step in steps:
            if step.status == StepStatus.running:
                step.status = StepStatus.cancelled
                step.completed_at = datetime.utcnow()
                await self.step_run_repository.update(step)
                logger.info(f"Cancelled running step {step.id}")

        # Step 5: Update pipeline status
        pipeline.status = PipelineStatus.cancelled
        pipeline.updated_at = datetime.utcnow()
        await self.pipeline_run_repository.update(pipeline)

        # Step 6: Emit audit event - AC-2.6.5
        if self.audit_service:
            try:
                await self.audit_service.log_event(
                    event_type="pipeline_cancelled",
                    tenant_id=command.tenant_id,
                    user_id=command.user_id,
                    resource_type="pipeline_run",
                    resource_id=pipeline.id,
                    metadata={
                        "reason": command.reason,
                        "previous_status": previous_status,
                        "steps_completed": completed_count,
                        "steps_cancelled": len(steps) - completed_count,
                    },
                )
            except Exception as e:
                # Log error but don't fail the cancellation
                logger.error(f"Failed to emit audit event: {e}")

        # Step 7: Return result
        steps_cancelled = len(steps) - completed_count
        message = (
            f"Pipeline cancelled successfully. "
            f"{completed_count} completed steps preserved."
        )

        logger.info(
            f"Pipeline {pipeline.id} cancelled. "
            f"Completed: {completed_count}, Cancelled: {steps_cancelled}"
        )

        return Return.ok(
            CancellationResultDTO(
                pipeline_run_id=pipeline.id,
                previous_status=previous_status,
                new_status=PipelineStatus.cancelled.value,
                steps_completed=completed_count,
                steps_cancelled=steps_cancelled,
                message=message,
            )
        )
