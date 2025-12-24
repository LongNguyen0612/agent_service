from libs.result import Result, Error, Return
from src.app.services.unit_of_work import UnitOfWork
from src.app.services.audit_service import AuditService
from src.app.services.input_spec_validator import InputSpecValidator
from src.app.repositories import ProjectRepository, TaskRepository
from src.adapter.repositories import SqlAlchemyProjectRepository, SqlAlchemyTaskRepository
from src.domain import Task, ProjectStatus
from .dtos import CreateTaskCommand, CreateTaskResponse


class CreateTaskUseCase:
    """Use case for creating a new task"""

    def __init__(
        self,
        uow: UnitOfWork,
        audit_service: AuditService,
        input_spec_validator: InputSpecValidator,
    ):
        self.uow = uow
        self.audit_service = audit_service
        self.input_spec_validator = input_spec_validator

    async def execute(self, command: CreateTaskCommand) -> Result[CreateTaskResponse]:
        """
        Execute the create task use case

        Returns:
            Result[CreateTaskResponse]: Success with task data or error
        """
        # AC-2.1.1: Validation - title cannot be empty
        if not command.title or len(command.title.strip()) == 0:
            return Return.err(Error(code="INVALID_INPUT", message="Task title cannot be empty"))

        # AC-2.1.2: Validate input_spec
        validation_result = self.input_spec_validator.validate(command.input_spec)
        if validation_result.is_err():
            return Return.err(validation_result.error)

        async with self.uow as session:
            # Create repositories
            project_repo: ProjectRepository = SqlAlchemyProjectRepository(session.session)
            task_repo: TaskRepository = SqlAlchemyTaskRepository(session.session)

            # AC-2.1.3: Verify project exists and is active
            project = await project_repo.get_by_id(command.project_id)
            if project is None:
                return Return.err(
                    Error(
                        code="PROJECT_NOT_FOUND", message=f"Project {command.project_id} not found"
                    )
                )

            # Verify project belongs to the same tenant (security check)
            if project.tenant_id != command.tenant_id:
                return Return.err(
                    Error(
                        code="PROJECT_NOT_FOUND", message=f"Project {command.project_id} not found"
                    )
                )

            if project.status != ProjectStatus.active:
                return Return.err(
                    Error(
                        code="PROJECT_NOT_ACTIVE",
                        message=f"Cannot create task in non-active project (status: {project.status})",
                    )
                )

            # Create task entity (status defaults to 'draft')
            task = Task(
                project_id=command.project_id,
                tenant_id=command.tenant_id,
                title=command.title.strip(),
                input_spec=command.input_spec,
            )

            # Persist task
            created_task = await task_repo.create(task)
            await self.uow.commit()

            # AC-2.1.4: Audit Logging
            await self.audit_service.log_event(
                event_type="task_created",
                tenant_id=command.tenant_id,
                user_id=command.user_id,
                resource_type="task",
                resource_id=created_task.id,
                metadata={
                    "task_title": created_task.title,
                    "project_id": created_task.project_id,
                    "status": created_task.status.value,
                },
            )

            # Return response DTO
            return Return.ok(
                CreateTaskResponse(
                    id=created_task.id,
                    project_id=created_task.project_id,
                    tenant_id=created_task.tenant_id,
                    title=created_task.title,
                    input_spec=created_task.input_spec,
                    status=created_task.status,
                    created_at=created_task.created_at,
                )
            )
