from libs.result import Result, Error, Return
from src.app.services.unit_of_work import UnitOfWork
from src.app.repositories import TaskRepository, ProjectRepository
from src.adapter.repositories import SqlAlchemyTaskRepository, SqlAlchemyProjectRepository
from .dtos import GetTaskResponse


class GetTaskByIdUseCase:
    """Use case for getting a single task by ID"""

    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def execute(self, task_id: str, tenant_id: str) -> Result[GetTaskResponse]:
        """
        Execute the get task by ID use case

        Args:
            task_id: ID of the task to retrieve
            tenant_id: ID of the tenant (for security check)

        Returns:
            Result[GetTaskResponse]: Success with task data or error
        """
        async with self.uow as session:
            # Create repositories
            task_repo: TaskRepository = SqlAlchemyTaskRepository(session.session)
            project_repo: ProjectRepository = SqlAlchemyProjectRepository(session.session)

            # Get task by ID with tenant isolation (security check built-in)
            task = await task_repo.get_by_id(task_id, tenant_id)

            if task is None:
                return Return.err(Error(code="TASK_NOT_FOUND", message="Task not found"))

            # Get project name
            project = await project_repo.get_by_id(task.project_id)
            project_name = project.name if project else "Unknown Project"

            # Convert to DTO
            task_dto = GetTaskResponse(
                id=str(task.id),
                project_id=str(task.project_id),
                project_name=project_name,
                tenant_id=str(task.tenant_id),
                title=task.title,
                input_spec=task.input_spec,
                status=task.status,
                created_at=task.created_at,
            )

            return Return.ok(task_dto)
