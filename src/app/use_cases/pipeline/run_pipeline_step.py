"""Run Pipeline Step Use Case - Story 2.4

Executes a single pipeline step with agent invocation and billing integration.
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any
from libs.result import Result, Return, Error
from src.domain.enums import (
    PipelineStatus,
    StepStatus,
    StepType,
    AgentType,
    ArtifactStatus,
    PauseReason,
)
from src.domain.base import generate_uuid
from src.domain.pipeline_run import PipelineRun
from src.domain.pipeline_step import PipelineStepRun
from src.domain.agent_run import AgentRun
from src.domain.artifact import Artifact
from src.domain.task import Task
from src.app.repositories.task_repository import TaskRepository
from src.app.repositories.pipeline_run_repository import IPipelineRunRepository
from src.app.repositories.pipeline_step_repository import IPipelineStepRunRepository
from src.app.repositories.agent_run_repository import IAgentRunRepository
from src.app.repositories.artifact_repository import IArtifactRepository
from src.app.repositories.dead_letter_event_repository import IDeadLetterEventRepository
from src.app.services.billing_client import BillingClient, InsufficientCreditsError
from src.app.services.agent_executor import AgentExecutor
from src.app.services.retry_scheduler import RetryScheduler
from src.app.use_cases.validate_pipeline import ValidatePipeline, ValidatePipelineCommandDTO
from src.domain.dead_letter_event import DeadLetterEvent
from .dtos import RunPipelineCommandDTO, PipelineStepResultDTO

logger = logging.getLogger(__name__)


# Agent type mapping - AC-2.4.2
STEP_TO_AGENT = {
    StepType.ANALYSIS: AgentType.ARCHITECT,
    StepType.USER_STORIES: AgentType.PM,
    StepType.CODE_SKELETON: AgentType.ENGINEER,
    StepType.TEST_CASES: AgentType.QA,
}


class RunPipelineStep:
    """
    Executes a pipeline step with agent invocation and billing - Story 2.4

    Implements:
    - AC-2.4.1: Pipeline run creation
    - AC-2.4.2: Agent execution
    - AC-2.4.3: Credit consumption after success
    - AC-2.4.4: Artifact creation
    - AC-2.4.5: Sequential step progression
    """

    def __init__(
        self,
        task_repository: TaskRepository,
        pipeline_run_repository: IPipelineRunRepository,
        step_run_repository: IPipelineStepRunRepository,
        agent_run_repository: IAgentRunRepository,
        artifact_repository: IArtifactRepository,
        billing_client: BillingClient,
        agent_executor: AgentExecutor,
        retry_scheduler: RetryScheduler = None,
        dead_letter_event_repository: IDeadLetterEventRepository = None,
    ):
        """
        Initialize RunPipelineStep use case.

        Args:
            task_repository: Repository for task lookup
            pipeline_run_repository: Repository for pipeline runs
            step_run_repository: Repository for step runs
            agent_run_repository: Repository for agent runs
            artifact_repository: Repository for artifacts
            billing_client: Client for billing service integration
            agent_executor: Executor for AI agents
            retry_scheduler: Scheduler for retry jobs (Story 2.5)
            dead_letter_event_repository: Repository for dead letter events (Story 2.5)
        """
        self.task_repository = task_repository
        self.pipeline_run_repository = pipeline_run_repository
        self.step_run_repository = step_run_repository
        self.agent_run_repository = agent_run_repository
        self.artifact_repository = artifact_repository
        self.billing_client = billing_client
        self.agent_executor = agent_executor
        self.retry_scheduler = retry_scheduler
        self.dead_letter_event_repository = dead_letter_event_repository

    async def execute(
        self, command: RunPipelineCommandDTO
    ) -> Result[PipelineStepResultDTO]:
        """
        Execute a pipeline step.

        Args:
            command: Command with task_id and tenant_id

        Returns:
            Result[PipelineStepResultDTO]: Step execution result

        Flow (AC-2.4.1 through AC-2.4.5):
        1. Validate preconditions
        2. Create or get existing PipelineRun
        3. Create PipelineStepRun (status=running)
        4. Capture input_snapshot
        5. Execute agent
        6. Create AgentRun record
        7. Create Artifact
        8. Update PipelineStepRun (status=completed)
        9. Consume credits
        10. Handle insufficient credits (pause pipeline)
        11. Update PipelineRun.current_step
        12. Return result
        """
        try:
            # Step 1: Get task
            task = await self.task_repository.get_by_id(
                task_id=command.task_id, tenant_id=command.tenant_id
            )
            if task is None:
                return Return.err(
                    Error(
                        code="TASK_NOT_FOUND",
                        message="Task not found or access denied",
                    )
                )

            # Step 2: Create or get existing PipelineRun - AC-2.4.1
            pipeline_run = await self._get_or_create_pipeline_run(task)

            # Check if pipeline was cancelled before starting new step - AC-2.6.4
            if pipeline_run.status == PipelineStatus.cancelled:
                return Return.err(
                    Error(
                        code="PIPELINE_CANCELLED",
                        message="Pipeline has been cancelled",
                    )
                )

            # Step 3: Create PipelineStepRun - AC-2.4.1
            step_type = self._get_step_type(pipeline_run.current_step)
            step_run = PipelineStepRun(
                id=generate_uuid(),
                pipeline_run_id=pipeline_run.id,
                step_number=pipeline_run.current_step,
                step_type=step_type,
                status=StepStatus.running,
                started_at=datetime.utcnow(),
                retry_count=0,
                max_retries=3,
            )
            step_run = await self.step_run_repository.create(step_run)

            # Step 4: Capture input_snapshot - AC-2.4.1
            input_snapshot = self._capture_input_snapshot(task, pipeline_run)
            step_run.input_snapshot = input_snapshot
            await self.step_run_repository.update(step_run)

            # Check for cancellation before executing agent - AC-2.6.4
            pipeline_run_check = await self.pipeline_run_repository.get_by_id(pipeline_run.id)
            if pipeline_run_check and pipeline_run_check.status == PipelineStatus.cancelled:
                # Mark step as cancelled and exit gracefully
                step_run.status = StepStatus.cancelled
                step_run.completed_at = datetime.utcnow()
                await self.step_run_repository.update(step_run)
                logger.info(f"Step {step_run.id} cancelled before agent execution")
                return Return.err(
                    Error(
                        code="PIPELINE_CANCELLED",
                        message="Pipeline was cancelled before step execution",
                    )
                )

            # Step 5: Execute agent - AC-2.4.2
            agent_type = STEP_TO_AGENT[step_type]
            try:
                agent_result = await self.agent_executor.execute(
                    agent_type=agent_type,
                    inputs={
                        "task_spec": task.input_spec,
                        "task_title": task.title,
                        "input_snapshot": input_snapshot,
                    },
                )
            except Exception as e:
                logger.error(f"Agent execution failed: {e}")
                step_run.status = StepStatus.failed
                step_run.completed_at = datetime.utcnow()
                await self.step_run_repository.update(step_run)

                # Story 2.5: Retry logic with exponential backoff
                if self.retry_scheduler and step_run.is_retryable():
                    # Schedule retry with exponential backoff
                    logger.info(f"Scheduling retry {step_run.retry_count + 1} for step {step_run.id}")
                    step_run.increment_retry()
                    step_run.status = StepStatus.pending  # Reset to pending for retry
                    await self.step_run_repository.update(step_run)
                    await self.retry_scheduler.schedule_retry(
                        step_run_id=step_run.id,
                        retry_count=step_run.retry_count
                    )
                    return Return.err(
                        Error(
                            code="AGENT_EXECUTION_FAILED_RETRY_SCHEDULED",
                            message=f"Agent execution failed, retry {step_run.retry_count}/{step_run.max_retries} scheduled",
                            reason=str(e),
                        )
                    )
                elif self.dead_letter_event_repository:
                    # Retries exhausted - create dead letter event
                    logger.error(f"Retries exhausted for step {step_run.id}, creating dead letter event")
                    dead_letter_event = DeadLetterEvent(
                        pipeline_run_id=pipeline_run.id,
                        step_run_id=step_run.id,
                        failure_reason=str(e),
                        retry_count=step_run.retry_count,
                        context={
                            "step_type": step_run.step_type.value,
                            "error_message": str(e),
                            "task_id": task.id,
                        }
                    )
                    await self.dead_letter_event_repository.create(dead_letter_event)

                    # Mark pipeline as failed
                    pipeline_run.status = PipelineStatus.failed
                    await self.pipeline_run_repository.update(pipeline_run)

                return Return.err(
                    Error(
                        code="AGENT_EXECUTION_FAILED",
                        message="Agent execution failed",
                        reason=str(e),
                    )
                )

            # Step 6: Create AgentRun record - AC-2.4.2
            agent_run = AgentRun(
                id=generate_uuid(),
                pipeline_run_id=pipeline_run.id,
                step_run_id=step_run.id,
                agent_type=agent_type,
                model="mock-model",  # MVP: hardcoded
                prompt_tokens=agent_result.prompt_tokens,
                completion_tokens=agent_result.completion_tokens,
                estimated_cost_credits=int(agent_result.estimated_cost_credits),
                actual_cost_credits=int(
                    agent_result.estimated_cost_credits
                ),  # MVP: same as estimate
                started_at=step_run.started_at,
                completed_at=datetime.utcnow(),
            )
            agent_run = await self.agent_run_repository.create(agent_run)

            # Step 7: Create Artifact - AC-2.4.4
            artifact_status = self._determine_artifact_status(step_type)
            artifact = Artifact(
                id=generate_uuid(),
                task_id=task.id,
                pipeline_run_id=pipeline_run.id,
                step_run_id=step_run.id,
                artifact_type=step_type.value,  # Use step_type as artifact_type
                status=artifact_status,
                content=agent_result.output,
                version=1,  # MVP: always 1
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            if artifact_status == ArtifactStatus.approved:
                artifact.approved_at = datetime.utcnow()

            artifact = await self.artifact_repository.create(artifact)

            # Step 8: Update PipelineStepRun - AC-2.4.4
            step_run.status = StepStatus.completed
            step_run.completed_at = datetime.utcnow()
            await self.step_run_repository.update(step_run)

            # Check for cancellation before billing - AC-2.6.4
            # If cancelled after agent completed but before billing, don't charge
            pipeline_run_check = await self.pipeline_run_repository.get_by_id(pipeline_run.id)
            if pipeline_run_check and pipeline_run_check.status == PipelineStatus.cancelled:
                logger.info(
                    f"Pipeline {pipeline_run.id} cancelled after step completion, "
                    f"skipping billing"
                )
                # Mark step as cancelled since we're not billing
                step_run.status = StepStatus.cancelled
                await self.step_run_repository.update(step_run)
                return Return.err(
                    Error(
                        code="PIPELINE_CANCELLED",
                        message="Pipeline was cancelled before billing",
                    )
                )

            # Step 9: Consume credits - AC-2.4.3, AC-2.5.5
            try:
                # AC-2.5.5: Include retry count in idempotency key
                if step_run.retry_count > 0:
                    idempotency_key = f"{pipeline_run.id}:{step_run.id}:retry_{step_run.retry_count}"
                else:
                    idempotency_key = f"{pipeline_run.id}:{step_run.id}"

                await self.billing_client.consume_credits(
                    tenant_id=command.tenant_id,
                    amount=Decimal(str(agent_run.actual_cost_credits)),
                    idempotency_key=idempotency_key,
                    reference_type="pipeline_step",
                    reference_id=step_run.id,
                    metadata={
                        "pipeline_run_id": pipeline_run.id,
                        "step_id": step_run.id,
                        "step_type": step_run.step_type.value,
                        "retry_count": step_run.retry_count,
                    },
                )
            except InsufficientCreditsError as e:
                # AC-2.4.3: Pause pipeline, do NOT rollback completed work
                logger.warning(
                    f"Insufficient credits after step completion: {e.message}"
                )
                pipeline_run.status = PipelineStatus.paused
                pipeline_run.add_pause_reason(PauseReason.INSUFFICIENT_CREDIT)
                pipeline_run.pause_expires_at = datetime.utcnow() + timedelta(days=7)
                await self.pipeline_run_repository.update(pipeline_run)

                return Return.ok(
                    PipelineStepResultDTO(
                        pipeline_run_id=pipeline_run.id,
                        step_number=step_run.step_number,
                        step_type=step_run.step_type.value,
                        status="paused_insufficient_credits",
                        artifact_id=artifact.id,
                    )
                )

            # Step 10: Update PipelineRun - AC-2.4.5
            if pipeline_run.current_step < 4:
                pipeline_run.current_step += 1

            pipeline_run.updated_at = datetime.utcnow()
            await self.pipeline_run_repository.update(pipeline_run)

            # Step 11: Return result
            logger.info(
                f"Pipeline step completed: pipeline_run_id={pipeline_run.id}, "
                f"step_number={step_run.step_number}, step_type={step_run.step_type}"
            )

            return Return.ok(
                PipelineStepResultDTO(
                    pipeline_run_id=pipeline_run.id,
                    step_number=step_run.step_number,
                    step_type=step_run.step_type.value,
                    status=step_run.status.value,
                    artifact_id=artifact.id,
                )
            )

        except Exception as e:
            logger.error(f"Unexpected error during pipeline execution: {e}")
            return Return.err(
                Error(
                    code="PIPELINE_EXECUTION_ERROR",
                    message="An unexpected error occurred during pipeline execution",
                    reason=str(e),
                )
            )

    async def _get_or_create_pipeline_run(self, task: Task) -> PipelineRun:
        """
        Get existing pipeline run or create new one - AC-2.4.1

        Args:
            task: Task to create pipeline for

        Returns:
            PipelineRun: Existing or newly created pipeline run
        """
        # Try to get existing pipeline run
        existing_run = await self.pipeline_run_repository.get_by_task_id(task.id)

        if existing_run and existing_run.status == PipelineStatus.running:
            return existing_run

        # Create new pipeline run
        pipeline_run = PipelineRun(
            id=generate_uuid(),
            task_id=task.id,
            tenant_id=task.tenant_id,
            status=PipelineStatus.running,
            current_step=1,
            pause_reasons=[],
            started_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        return await self.pipeline_run_repository.create(pipeline_run)

    def _get_step_type(self, step_number: int) -> StepType:
        """
        Get step type for given step number.

        Args:
            step_number: Step number (1-4)

        Returns:
            StepType: Corresponding step type
        """
        step_mapping = {
            1: StepType.ANALYSIS,
            2: StepType.USER_STORIES,
            3: StepType.CODE_SKELETON,
            4: StepType.TEST_CASES,
        }
        return step_mapping[step_number]

    def _capture_input_snapshot(
        self, task: Task, pipeline_run: PipelineRun
    ) -> Dict[str, Any]:
        """
        Capture immutable input snapshot - AC-2.4.1

        Args:
            task: Task being processed
            pipeline_run: Current pipeline run

        Returns:
            Dict: Input snapshot
        """
        return {
            "task_id": task.id,
            "task_title": task.title,
            "task_input_spec": task.input_spec,
            "pipeline_run_id": pipeline_run.id,
            "current_step": pipeline_run.current_step,
            "snapshot_at": datetime.utcnow().isoformat(),
        }

    def _determine_artifact_status(self, step_type: StepType) -> ArtifactStatus:
        """
        Determine artifact status based on step type - AC-2.4.4

        ANALYSIS step is auto-approved.
        USER_STORIES step requires user approval (status=draft).

        Args:
            step_type: Type of step

        Returns:
            ArtifactStatus: Artifact status
        """
        if step_type == StepType.ANALYSIS:
            return ArtifactStatus.approved
        else:
            return ArtifactStatus.draft
