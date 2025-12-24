from libs.result import Result, Error, Return
from src.app.services.unit_of_work import UnitOfWork
from src.app.repositories import ProjectRepository, TaskRepository
from src.adapter.repositories import SqlAlchemyProjectRepository, SqlAlchemyTaskRepository
from .dtos import ProjectDTO


class GetProjectByIdUseCase:
    """Use case for getting a single project by ID"""

    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def execute(self, project_id: str, tenant_id: str) -> Result[ProjectDTO]:
        """
        Execute the get project by ID use case

        Args:
            project_id: ID of the project to retrieve
            tenant_id: ID of the tenant (for security check)

        Returns:
            Result[ProjectDTO]: Success with project data or error
        """
        async with self.uow as session:
            # Create repositories
            project_repo: ProjectRepository = SqlAlchemyProjectRepository(session.session)
            task_repo: TaskRepository = SqlAlchemyTaskRepository(session.session)

            # Get project by ID
            project = await project_repo.get_by_id(project_id)

            if project is None:
                return Return.err(Error(code="NOT_FOUND", message="Project not found"))

            # Security check: ensure project belongs to the tenant
            if str(project.tenant_id) != tenant_id:
                return Return.err(
                    Error(code="INSUFFICIENT_PERMISSIONS", message="Access denied")
                )

            # Get task count for this project
            tasks = await task_repo.find_by_project_id(project_id, tenant_id)
            task_count = len(tasks)

            # Convert to DTO
            project_dto = ProjectDTO(
                id=str(project.id),
                tenant_id=str(project.tenant_id),
                name=project.name,
                description=project.description,
                status=project.status,
                created_at=project.created_at,
                updated_at=project.updated_at,
                task_count=task_count,
            )

            return Return.ok(project_dto)
