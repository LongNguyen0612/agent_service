from libs.result import Result, Return
from src.app.services.unit_of_work import UnitOfWork
from src.app.repositories import ProjectRepository, TaskRepository
from src.adapter.repositories import SqlAlchemyProjectRepository, SqlAlchemyTaskRepository
from .dtos import GetProjectsResponse, ProjectDTO


class GetProjectsUseCase:
    """Use case for getting all projects for a tenant"""

    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def execute(self, tenant_id: str) -> Result[GetProjectsResponse]:
        """
        Execute the get projects use case

        Args:
            tenant_id: ID of the tenant to get projects for

        Returns:
            Result[GetProjectsResponse]: Success with list of projects or error
        """
        async with self.uow as session:
            # Create repositories
            project_repo: ProjectRepository = SqlAlchemyProjectRepository(session.session)
            task_repo: TaskRepository = SqlAlchemyTaskRepository(session.session)

            # Get all projects for the tenant
            projects = await project_repo.get_by_tenant_id(tenant_id)

            # Get task counts for each project
            project_dtos = []
            for project in projects:
                tasks = await task_repo.find_by_project_id(project.id, tenant_id)
                task_count = len(tasks)

                project_dtos.append(
                    ProjectDTO(
                        id=str(project.id),
                        tenant_id=str(project.tenant_id),
                        name=project.name,
                        description=project.description,
                        status=project.status,
                        created_at=project.created_at,
                        updated_at=project.updated_at,
                        task_count=task_count,
                    )
                )

            return Return.ok(GetProjectsResponse(projects=project_dtos))
