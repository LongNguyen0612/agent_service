"""
Pipeline Executor Service - Orchestrates linear step-by-step pipeline execution
"""

from typing import Dict, Any, Callable, Awaitable, List, Optional
from src.domain import Task, PipelineRun, PipelineStep
from src.domain.enums import PipelineStepStatus, ArtifactType, StepType
from src.app.repositories.pipeline_run_repository import IPipelineRunRepository
from src.app.repositories.pipeline_step_repository import IPipelineStepRunRepository
from src.app.repositories.task_repository import TaskRepository
from src.app.services.audit_service import AuditService
from src.app.services.artifact_service import ArtifactService


# Type alias for step handler functions
StepHandler = Callable[[Dict[str, Any], str], Awaitable[Dict[str, Any]]]


class PipelineExecutor:
    """
    Executes a linear pipeline of steps for a task.

    Pipeline flow:
    1. Create PipelineRun with status=running
    2. Create all PipelineSteps with status=pending
    3. Execute steps sequentially (1 → 2 → 3 → 4)
    4. Each step: pending → running → completed (or failed)
    5. If any step fails, mark task as failed and stop execution
    6. If all steps complete, mark task as completed
    """

    # Hardcoded linear pipeline steps for MVP
    PIPELINE_STEPS = [
        {"step_number": 1, "step_name": "validate_input", "step_type": StepType.ANALYSIS},
        {"step_number": 2, "step_name": "generate_prd", "step_type": StepType.ANALYSIS},
        {"step_number": 3, "step_name": "generate_stories", "step_type": StepType.USER_STORIES},
        {"step_number": 4, "step_name": "review_output", "step_type": StepType.ANALYSIS},
    ]

    def __init__(
        self,
        task_repo: TaskRepository,
        pipeline_run_repo: IPipelineRunRepository,
        pipeline_step_repo: IPipelineStepRunRepository,
        audit_service: AuditService,
        step_handlers: Dict[str, StepHandler],
        artifact_service: Optional[ArtifactService] = None,
    ):
        self.task_repo = task_repo
        self.pipeline_run_repo = pipeline_run_repo
        self.pipeline_step_repo = pipeline_step_repo
        self.audit_service = audit_service
        self.step_handlers = step_handlers
        self.artifact_service = artifact_service

    async def execute(self, task: Task) -> None:
        """
        Execute the full pipeline for a task.

        Args:
            task: The task to execute (must be in 'queued' status)

        Raises:
            ValueError: If task is not in queued status
        """
        if task.status.value != "queued":
            raise ValueError(f"Task must be in 'queued' status, got '{task.status.value}'")

        # Transition task to running
        task.transition_to_running()
        await self.task_repo.update(task)

        # Create pipeline run
        from datetime import datetime
        pipeline_run = PipelineRun(task_id=task.id, tenant_id=task.tenant_id, started_at=datetime.utcnow())
        pipeline_run = await self.pipeline_run_repo.create(pipeline_run)

        # Log audit event: pipeline started
        await self.audit_service.log_event(
            event_type="pipeline_started",
            tenant_id=task.tenant_id,
            user_id=None,  # System-generated event
            resource_type="pipeline_run",
            resource_id=pipeline_run.id,
            metadata={"task_id": task.id, "task_title": task.title},
        )

        # Create all pipeline steps
        steps: List[PipelineStep] = []
        for step_def in self.PIPELINE_STEPS:
            step = PipelineStep(
                pipeline_run_id=pipeline_run.id,
                step_number=step_def["step_number"],
                step_name=step_def["step_name"],
                step_type=step_def["step_type"],
                status=PipelineStepStatus.pending,
            )
            created_step = await self.pipeline_step_repo.create(step)
            steps.append(created_step)

        # Execute steps sequentially
        try:
            context: Dict[str, Any] = {"input_spec": task.input_spec}

            for step in steps:
                # Execute the step
                step_output = await self._execute_step(step, context, task.tenant_id)

                # Merge step output into context for next step
                if step_output:
                    context.update(step_output)

            # All steps completed successfully
            pipeline_run.mark_completed()
            await self.pipeline_run_repo.update(pipeline_run)

            task.transition_to_completed()
            await self.task_repo.update(task)

            # Log audit event: pipeline completed
            await self.audit_service.log_event(
                event_type="pipeline_completed",
                tenant_id=task.tenant_id,
                user_id=None,
                resource_type="pipeline_run",
                resource_id=pipeline_run.id,
                metadata={"task_id": task.id, "total_steps": len(steps)},
            )

        except Exception as e:
            # Pipeline failed - mark everything as failed
            error_message = str(e)

            pipeline_run.mark_failed(error_message)
            await self.pipeline_run_repo.update(pipeline_run)

            task.transition_to_failed()
            await self.task_repo.update(task)

            # Log audit event: pipeline failed
            await self.audit_service.log_event(
                event_type="pipeline_failed",
                tenant_id=task.tenant_id,
                user_id=None,
                resource_type="pipeline_run",
                resource_id=pipeline_run.id,
                metadata={
                    "task_id": task.id,
                    "error_message": error_message,
                    "failed_step": None,  # Could be enhanced to track which step failed
                },
            )

            # Re-raise the exception for visibility
            raise

    async def _execute_step(
        self, step: PipelineStep, context: Dict[str, Any], tenant_id: str
    ) -> Dict[str, Any]:
        """
        Execute a single pipeline step.

        Args:
            step: The step to execute
            context: Accumulated context from previous steps
            tenant_id: Tenant ID for audit logging

        Returns:
            Dict containing step output (merged into context for next step)

        Raises:
            Exception: If step handler fails
        """
        # Mark step as running
        step.mark_running()
        await self.pipeline_step_repo.update(step)

        try:
            # Get the handler for this step
            handler = self.step_handlers.get(step.step_name)
            if not handler:
                raise ValueError(f"No handler found for step '{step.step_name}'")

            # Execute the handler
            step_output = await handler(context, tenant_id)

            # Mark step as completed
            step.mark_completed(output=step_output)
            await self.pipeline_step_repo.update(step)

            # Create artifact if step produces one (Story 4.1)
            await self._create_artifact_if_needed(step, step_output, tenant_id)

            return step_output

        except Exception as e:
            # Mark step as failed
            error_message = f"{step.step_name} failed: {str(e)}"
            step.mark_failed(error_message)
            await self.pipeline_step_repo.update(step)

            # Re-raise for pipeline-level failure handling
            raise Exception(error_message) from e

    async def _create_artifact_if_needed(
        self, step: PipelineStep, step_output: Dict[str, Any], tenant_id: str
    ) -> None:
        """
        Create an artifact if the step produced output that should be stored

        Artifact creation rules (MVP):
        - Step 2 (generate_prd): Creates "document" artifact with PRD content
        - Step 3 (generate_stories): Creates "code" artifact with stories content

        Args:
            step: The completed pipeline step
            step_output: Output from the step handler
            tenant_id: Tenant ID for artifact isolation
        """
        if not self.artifact_service:
            return  # Artifact service not configured

        # Determine if this step should produce an artifact
        artifact_mapping = {
            2: {  # generate_prd step
                "content_key": "prd_content",
                "artifact_type": ArtifactType.document,
            },
            3: {  # generate_stories step
                "content_key": "stories_content",
                "artifact_type": ArtifactType.code,
            },
        }

        mapping = artifact_mapping.get(step.step_number)
        if not mapping:
            return  # This step doesn't produce artifacts

        content_key = mapping["content_key"]
        artifact_type = mapping["artifact_type"]

        # Extract content from step output
        content = step_output.get(content_key)
        if not content:
            return  # No content to store

        # Extract task_id from pipeline run
        # We need to get the PipelineRun to get the task_id
        # For now, we'll assume step_output contains task_id (could be added to context)
        # Or we fetch it from the database
        from src.adapter.repositories.pipeline_run_repository import PipelineRunRepository

        # This is a bit of a hack - ideally we'd pass task_id through context
        # For MVP, we'll fetch it
        pipeline_run = await self.pipeline_run_repo.get_by_id(step.pipeline_run_id)
        if not pipeline_run:
            return

        # Create artifact
        await self.artifact_service.create_artifact(
            task_id=pipeline_run.task_id,
            pipeline_run_id=step.pipeline_run_id,
            step_run_id=step.id,
            artifact_type=artifact_type,
            content=content,
            metadata={
                "step_name": step.step_name,
                "step_number": step.step_number,
                "generated_at": step.completed_at.isoformat() if step.completed_at else None,
            },
        )
