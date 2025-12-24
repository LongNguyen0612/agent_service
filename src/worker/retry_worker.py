"""Retry Worker - Story 2.5

Background worker that processes retry jobs with exponential backoff.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from src.app.repositories.retry_job_repository import IRetryJobRepository
from src.app.repositories.pipeline_step_repository import IPipelineStepRunRepository
from src.app.repositories.dead_letter_event_repository import IDeadLetterEventRepository
from src.app.repositories.pipeline_run_repository import IPipelineRunRepository
from src.app.repositories.task_repository import TaskRepository
from src.app.repositories.agent_run_repository import IAgentRunRepository
from src.app.repositories.artifact_repository import IArtifactRepository
from src.app.services.billing_client import BillingClient, InsufficientCreditsError, BillingServiceUnavailable
from src.app.services.agent_executor import AgentExecutor
from src.app.services.retry_scheduler import RetryScheduler
from src.adapter.repositories.retry_job_repository import RetryJobRepository
from src.adapter.repositories.pipeline_step_repository import PipelineStepRunRepository
from src.adapter.repositories.dead_letter_event_repository import DeadLetterEventRepository
from src.adapter.repositories.pipeline_run_repository import PipelineRunRepository
from src.adapter.repositories.task_repository import TaskRepository as SqlAlchemyTaskRepository
from src.adapter.repositories.agent_run_repository import AgentRunRepository
from src.adapter.repositories.artifact_repository import ArtifactRepository
from src.adapter.services.http_billing_client import HttpBillingClient
from src.adapter.services.mock_agent_executor import MockAgentExecutor
from src.domain.retry_job import RetryJob
from src.domain.pipeline_step import PipelineStepRun
from src.domain.pipeline_run import PipelineRun
from src.domain.dead_letter_event import DeadLetterEvent
from src.domain.agent_run import AgentRun
from src.domain.artifact import Artifact
from src.domain.base import generate_uuid
from src.domain.enums import (
    RetryStatus, StepStatus, PipelineStatus, AgentType, StepType,
    ArtifactStatus, PauseReason
)

logger = logging.getLogger(__name__)

# Agent type mapping - same as RunPipelineStep
STEP_TO_AGENT = {
    StepType.ANALYSIS: AgentType.ARCHITECT,
    StepType.USER_STORIES: AgentType.PM,
    StepType.CODE_SKELETON: AgentType.ENGINEER,
    StepType.TEST_CASES: AgentType.QA,
}


class RetryWorker:
    """
    Background worker that processes retry jobs - AC-2.5.2

    Polls for due retry jobs and re-executes failed pipeline steps.
    """

    def __init__(
        self,
        retry_job_repository: IRetryJobRepository,
        step_run_repository: IPipelineStepRunRepository,
        dead_letter_event_repository: IDeadLetterEventRepository,
        pipeline_run_repository: IPipelineRunRepository,
        task_repository: TaskRepository,
        agent_run_repository: IAgentRunRepository,
        artifact_repository: IArtifactRepository,
        billing_client: BillingClient,
        agent_executor: AgentExecutor,
        retry_scheduler: RetryScheduler,
        poll_interval: int = 5,
    ):
        """
        Initialize RetryWorker.

        Args:
            retry_job_repository: Repository for retry jobs
            step_run_repository: Repository for pipeline step runs
            dead_letter_event_repository: Repository for dead letter events
            pipeline_run_repository: Repository for pipeline runs
            task_repository: Repository for tasks
            agent_run_repository: Repository for agent runs
            artifact_repository: Repository for artifacts
            billing_client: Client for billing service integration
            agent_executor: Executor for AI agents
            retry_scheduler: Scheduler for retry jobs
            poll_interval: Polling interval in seconds (default: 5)
        """
        self.retry_job_repository = retry_job_repository
        self.step_run_repository = step_run_repository
        self.dead_letter_event_repository = dead_letter_event_repository
        self.pipeline_run_repository = pipeline_run_repository
        self.task_repository = task_repository
        self.agent_run_repository = agent_run_repository
        self.artifact_repository = artifact_repository
        self.billing_client = billing_client
        self.agent_executor = agent_executor
        self.retry_scheduler = retry_scheduler
        self.poll_interval = poll_interval
        self.running = False

    async def start(self):
        """
        Start the retry worker.

        Continuously polls for due retry jobs and processes them.
        """
        self.running = True
        logger.info("RetryWorker started")

        while self.running:
            try:
                await self._process_due_jobs()
            except Exception as e:
                logger.error(f"Error processing retry jobs: {e}")

            # Sleep for poll interval
            await asyncio.sleep(self.poll_interval)

    async def stop(self):
        """Stop the retry worker."""
        self.running = False
        logger.info("RetryWorker stopped")

    async def _process_due_jobs(self):
        """Process all due retry jobs."""
        due_jobs = await self.retry_job_repository.get_due_jobs()

        if due_jobs:
            logger.info(f"Found {len(due_jobs)} due retry jobs")

        for job in due_jobs:
            try:
                await self._process_retry_job(job)
            except Exception as e:
                logger.error(f"Error processing retry job {job.id}: {e}")
                # Mark job as failed
                await self.retry_job_repository.update_status(job.id, RetryStatus.failed)

    async def _process_retry_job(self, job: RetryJob):
        """
        Process a single retry job.

        Args:
            job: RetryJob to process
        """
        logger.info(f"Processing retry job {job.id} for step {job.step_run_id}")

        # Mark job as processing
        job.mark_processing()
        await self.retry_job_repository.update_status(job.id, RetryStatus.processing)

        # Get step run
        step_run = await self.step_run_repository.get_by_id(job.step_run_id)
        if not step_run:
            logger.error(f"Step run {job.step_run_id} not found")
            job.mark_failed()
            await self.retry_job_repository.update_status(job.id, RetryStatus.failed)
            return

        # TODO: Re-execute the pipeline step using RunPipelineStep
        # For now, this is a placeholder that would need to:
        # 1. Get the task and pipeline_run
        # 2. Re-run the agent executor with the same input_snapshot
        # 3. Handle success/failure
        #
        # In a real implementation, you would inject RunPipelineStep or
        # create a separate execute_step_retry method that reuses the logic

        # For demonstration, let's assume the retry succeeds
        # In reality, you'd call the actual execution logic here
        retry_succeeded = await self._execute_step_retry(step_run)

        if retry_succeeded:
            # Retry succeeded
            step_run.status = StepStatus.completed
            step_run.completed_at = datetime.utcnow()
            await self.step_run_repository.update(step_run)

            job.mark_completed()
            await self.retry_job_repository.update_status(job.id, RetryStatus.completed)
            logger.info(f"Retry job {job.id} completed successfully")
        else:
            # Retry failed
            if step_run.retry_count >= step_run.max_retries:
                # Retries exhausted - create dead letter event
                logger.error(f"Retries exhausted for step {step_run.id}")
                await self._create_dead_letter_event(step_run)

                # Mark pipeline as failed
                pipeline_run = await self.pipeline_run_repository.get_by_id(
                    step_run.pipeline_run_id
                )
                if pipeline_run:
                    pipeline_run.status = PipelineStatus.failed
                    await self.pipeline_run_repository.update(pipeline_run)

                job.mark_failed()
                await self.retry_job_repository.update_status(job.id, RetryStatus.failed)
            else:
                # More retries available - will be scheduled by RunPipelineStep
                job.mark_failed()
                await self.retry_job_repository.update_status(job.id, RetryStatus.failed)

    async def _execute_step_retry(self, step_run: PipelineStepRun) -> bool:
        """
        Execute the retry for a pipeline step - AC-2.5.2

        Full implementation that:
        1. Gets the pipeline run and task context
        2. Re-runs the agent executor with the stored input_snapshot
        3. Creates artifact and agent run records on success
        4. Handles billing with retry-specific idempotency key
        5. Returns success/failure

        Args:
            step_run: PipelineStepRun to retry

        Returns:
            bool: True if retry succeeded, False otherwise
        """
        try:
            # 1. Get pipeline run context
            pipeline_run = await self.pipeline_run_repository.get_by_id(
                step_run.pipeline_run_id
            )
            if not pipeline_run:
                logger.error(f"Pipeline run {step_run.pipeline_run_id} not found")
                return False

            # Check if pipeline was cancelled
            if pipeline_run.status == PipelineStatus.cancelled:
                logger.info(f"Pipeline {pipeline_run.id} was cancelled, skipping retry")
                step_run.status = StepStatus.cancelled
                await self.step_run_repository.update(step_run)
                return False

            # 2. Get task context
            task = await self.task_repository.get_by_id(
                task_id=pipeline_run.task_id,
                tenant_id=pipeline_run.tenant_id
            )
            if not task:
                logger.error(f"Task {pipeline_run.task_id} not found")
                return False

            # 3. Mark step as running for retry
            step_run.status = StepStatus.running
            step_run.started_at = datetime.utcnow()
            await self.step_run_repository.update(step_run)

            # 4. Execute agent using stored input_snapshot - AC-2.5.2
            step_type = step_run.step_type
            if isinstance(step_type, str):
                step_type = StepType(step_type)
            agent_type = STEP_TO_AGENT.get(step_type)

            if not agent_type:
                logger.error(f"Unknown step type: {step_run.step_type}")
                return False

            # Use input_snapshot if available, otherwise create from task
            inputs = step_run.input_snapshot or {
                "task_spec": task.input_spec,
                "task_title": task.title,
            }

            try:
                agent_result = await self.agent_executor.execute(
                    agent_type=agent_type,
                    inputs=inputs,
                )
            except Exception as e:
                logger.error(f"Agent execution failed on retry: {e}")
                step_run.status = StepStatus.failed
                step_run.error_message = str(e)
                step_run.completed_at = datetime.utcnow()
                await self.step_run_repository.update(step_run)
                return False

            # 5. Create AgentRun record
            agent_run = AgentRun(
                id=generate_uuid(),
                pipeline_run_id=pipeline_run.id,
                step_run_id=step_run.id,
                agent_type=agent_type,
                model="mock-model",
                prompt_tokens=agent_result.prompt_tokens,
                completion_tokens=agent_result.completion_tokens,
                estimated_cost_credits=int(agent_result.estimated_cost_credits),
                actual_cost_credits=int(agent_result.estimated_cost_credits),
                started_at=step_run.started_at,
                completed_at=datetime.utcnow(),
            )
            await self.agent_run_repository.create(agent_run)

            # 6. Create Artifact
            artifact_status = (
                ArtifactStatus.approved if step_type == StepType.ANALYSIS
                else ArtifactStatus.draft
            )
            artifact = Artifact(
                id=generate_uuid(),
                task_id=task.id,
                pipeline_run_id=pipeline_run.id,
                step_run_id=step_run.id,
                artifact_type=step_type.value,
                status=artifact_status,
                content=agent_result.output,
                version=1,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            if artifact_status == ArtifactStatus.approved:
                artifact.approved_at = datetime.utcnow()
            await self.artifact_repository.create(artifact)

            # 7. Mark step as completed
            step_run.status = StepStatus.completed
            step_run.completed_at = datetime.utcnow()
            step_run.output = agent_result.output
            await self.step_run_repository.update(step_run)

            # 8. Consume credits with retry-specific idempotency key - AC-2.5.5
            try:
                idempotency_key = f"{pipeline_run.id}:{step_run.id}:retry_{step_run.retry_count}"
                await self.billing_client.consume_credits(
                    tenant_id=pipeline_run.tenant_id,
                    amount=Decimal(str(agent_run.actual_cost_credits)),
                    idempotency_key=idempotency_key,
                    reference_type="pipeline_step_retry",
                    reference_id=step_run.id,
                    metadata={
                        "pipeline_run_id": pipeline_run.id,
                        "step_id": step_run.id,
                        "step_type": step_type.value,
                        "retry_count": step_run.retry_count,
                    },
                )
            except InsufficientCreditsError as e:
                # Pause pipeline on insufficient credits
                logger.warning(f"Insufficient credits on retry: {e.message}")
                pipeline_run.status = PipelineStatus.paused
                pipeline_run.add_pause_reason(PauseReason.INSUFFICIENT_CREDIT)
                pipeline_run.pause_expires_at = datetime.utcnow() + timedelta(days=7)
                await self.pipeline_run_repository.update(pipeline_run)
                # Step completed but billing failed - still return True
                return True
            except BillingServiceUnavailable as e:
                # Log but don't fail the step - billing can be retried
                logger.error(f"Billing service unavailable: {e.message}")

            # 9. Update pipeline progress if not at final step
            if pipeline_run.current_step < 4:
                pipeline_run.current_step += 1
                pipeline_run.updated_at = datetime.utcnow()
                await self.pipeline_run_repository.update(pipeline_run)

            logger.info(
                f"Retry successful for step {step_run.id}, "
                f"retry_count={step_run.retry_count}"
            )
            return True

        except Exception as e:
            logger.error(f"Unexpected error during step retry: {e}")
            step_run.status = StepStatus.failed
            step_run.error_message = str(e)
            step_run.completed_at = datetime.utcnow()
            await self.step_run_repository.update(step_run)
            return False

    async def _create_dead_letter_event(self, step_run: PipelineStepRun):
        """
        Create a dead letter event for an exhausted step.

        Args:
            step_run: Failed PipelineStepRun with exhausted retries
        """
        dead_letter_event = DeadLetterEvent(
            pipeline_run_id=step_run.pipeline_run_id,
            step_run_id=step_run.id,
            failure_reason="Retries exhausted",
            retry_count=step_run.retry_count,
            context={
                "step_type": step_run.step_type.value,
                "step_number": step_run.step_number,
                "max_retries": step_run.max_retries,
            },
        )
        await self.dead_letter_event_repository.create(dead_letter_event)
        logger.info(f"Created dead letter event for step {step_run.id}")


async def run_retry_worker(database_url: str, billing_service_url: str = "http://localhost:8000"):
    """
    Main entry point for running the retry worker.

    Args:
        database_url: Database connection URL
        billing_service_url: Billing service base URL
    """
    # Create async engine and session factory
    engine = create_async_engine(database_url, echo=False)
    AsyncSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    async with AsyncSessionLocal() as session:
        # Initialize repositories
        retry_job_repo = RetryJobRepository(session)
        step_run_repo = PipelineStepRunRepository(session)
        dead_letter_repo = DeadLetterEventRepository(session)
        pipeline_run_repo = PipelineRunRepository(session)
        task_repo = SqlAlchemyTaskRepository(session)
        agent_run_repo = AgentRunRepository(session)
        artifact_repo = ArtifactRepository(session)

        # Initialize services
        billing_client = HttpBillingClient(base_url=billing_service_url)
        agent_executor = MockAgentExecutor()
        retry_scheduler = RetryScheduler(retry_job_repository=retry_job_repo)

        # Create and start worker
        worker = RetryWorker(
            retry_job_repository=retry_job_repo,
            step_run_repository=step_run_repo,
            dead_letter_event_repository=dead_letter_repo,
            pipeline_run_repository=pipeline_run_repo,
            task_repository=task_repo,
            agent_run_repository=agent_run_repo,
            artifact_repository=artifact_repo,
            billing_client=billing_client,
            agent_executor=agent_executor,
            retry_scheduler=retry_scheduler,
        )

        try:
            await worker.start()
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
            await worker.stop()
        finally:
            await engine.dispose()


if __name__ == "__main__":
    """
    Entry point for running the retry worker as a standalone process.

    Usage:
        cd agent_service
        uv run python -m src.worker.retry_worker

    Or with custom settings:
        DB_URI="postgresql+asyncpg://..." BILLING_URL="http://..." uv run python -m src.worker.retry_worker
    """
    import os
    import sys

    # Add parent directory to path for imports
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Get configuration from environment or defaults
    database_url = os.environ.get(
        "DB_URI",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/agent_service"
    )
    billing_url = os.environ.get(
        "BILLING_SERVICE_URL",
        "http://localhost:8000"
    )

    logger.info(f"Starting RetryWorker with DB: {database_url[:50]}...")
    logger.info(f"Billing service URL: {billing_url}")

    # Run the worker
    asyncio.run(run_retry_worker(database_url, billing_url))
