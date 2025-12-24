"""
Queue Task Use Case - Transitions task to queued and triggers pipeline execution
"""

from libs.result import Result, Error, Return
from src.app.services.unit_of_work import UnitOfWork
from src.app.services.audit_service import AuditService
from src.app.services.pipeline_executor import PipelineExecutor
from src.app.services.pipeline_handlers import PIPELINE_HANDLERS
from src.app.repositories import TaskRepository
from src.adapter.repositories import (
    SqlAlchemyTaskRepository,
    PipelineRunRepository,
    PipelineStepRunRepository,
)
from src.domain.enums import TaskStatus
from .dtos import QueueTaskResponse


class QueueTaskUseCase:
    """Use case for queuing a task and triggering pipeline execution"""

    def __init__(self, uow: UnitOfWork, audit_service: AuditService):
        self.uow = uow
        self.audit_service = audit_service

    async def execute(self, task_id: str, tenant_id: str) -> Result[QueueTaskResponse]:
        """
        Queue a task for execution (draft → queued → pipeline execution)

        Args:
            task_id: ID of the task to queue
            tenant_id: Tenant ID for authorization

        Returns:
            Result[QueueTaskResponse]: Success or error
        """
        async with self.uow as session:
            task_repo: TaskRepository = SqlAlchemyTaskRepository(session.session)

            # Get task
            task = await task_repo.get_by_id(task_id, tenant_id)
            if task is None:
                return Return.err(Error(code="TASK_NOT_FOUND", message=f"Task {task_id} not found"))

            # Verify task is in draft status
            if task.status != TaskStatus.draft:
                return Return.err(
                    Error(
                        code="INVALID_TASK_STATUS",
                        message=f"Task must be in 'draft' status, currently '{task.status.value}'",
                    )
                )

            # Transition to queued
            task.transition_to_queued()
            await task_repo.update(task)
            await self.uow.commit()

            # Return response (pipeline will be executed in background)
            return Return.ok(
                QueueTaskResponse(
                    id=task.id,
                    status=task.status,
                    message="Task queued for execution",
                )
            )

    async def execute_pipeline_in_background(self, task_id: str, tenant_id: str) -> None:
        """
        Execute the pipeline for a queued task (called from BackgroundTasks)

        This method is meant to be called asynchronously via FastAPI BackgroundTasks.
        It runs in a separate database session.

        Args:
            task_id: ID of the task to execute
            tenant_id: Tenant ID for authorization
        """
        # Create a new database session for background execution
        async with self.uow as session:
            # Create repositories
            task_repo = SqlAlchemyTaskRepository(session.session)
            pipeline_run_repo = PipelineRunRepository(session.session)
            pipeline_step_repo = PipelineStepRunRepository(session.session)

            # Import artifact repository
            from src.adapter.repositories.artifact_repository import ArtifactRepository
            from src.app.services.artifact_service import ArtifactService

            artifact_repo = ArtifactRepository(session.session)

            # Get task
            task = await task_repo.get_by_id(task_id, tenant_id)
            if task is None:
                # Log error - task disappeared
                await self.audit_service.log_event(
                    event_type="pipeline_error",
                    tenant_id=tenant_id,
                    user_id=None,
                    resource_type="task",
                    resource_id=task_id,
                    metadata={"error": "Task not found during pipeline execution"},
                )
                return

            # Create artifact service
            artifact_service = ArtifactService(artifact_repo=artifact_repo)

            # Create pipeline executor
            executor = PipelineExecutor(
                task_repo=task_repo,
                pipeline_run_repo=pipeline_run_repo,
                pipeline_step_repo=pipeline_step_repo,
                audit_service=self.audit_service,
                step_handlers=PIPELINE_HANDLERS,
                artifact_service=artifact_service,
            )

            # Execute pipeline
            try:
                await executor.execute(task)
                await self.uow.commit()
            except Exception as e:
                # Pipeline execution failed - error already logged by executor
                await self.uow.rollback()
                # Re-raise for logging visibility
                print(f"Pipeline execution failed for task {task_id}: {str(e)}")
