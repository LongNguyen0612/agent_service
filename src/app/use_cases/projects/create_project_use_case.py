from libs.result import Result, Error, Return
from src.app.services.unit_of_work import UnitOfWork
from src.app.services.audit_service import AuditService
from src.app.repositories import ProjectRepository
from src.adapter.repositories import SqlAlchemyProjectRepository
from src.domain import Project
from .dtos import CreateProjectCommand, CreateProjectResponse


class CreateProjectUseCase:
    """Use case for creating a new project"""

    def __init__(self, uow: UnitOfWork, audit_service: AuditService):
        self.uow = uow
        self.audit_service = audit_service

    async def execute(self, command: CreateProjectCommand) -> Result[CreateProjectResponse]:
        """
        Execute the create project use case

        Returns:
            Result[CreateProjectResponse]: Success with project data or error
        """
        # Validation
        if not command.name or len(command.name.strip()) == 0:
            return Return.err(Error(code="INVALID_INPUT", message="Project name cannot be empty"))

        async with self.uow as session:
            # Create repository
            project_repo: ProjectRepository = SqlAlchemyProjectRepository(session.session)

            # Create project entity
            project = Project(
                tenant_id=command.tenant_id,
                name=command.name.strip(),
                description=command.description,
            )

            # Persist project
            created_project = await project_repo.create(project)
            await self.uow.commit()

            # Log audit event
            await self.audit_service.log_event(
                event_type="project_created",
                tenant_id=command.tenant_id,
                user_id=command.user_id,
                resource_type="project",
                resource_id=created_project.id,
                metadata={"project_name": created_project.name},
            )

            # Return response DTO
            return Return.ok(
                CreateProjectResponse(
                    id=created_project.id,
                    tenant_id=created_project.tenant_id,
                    name=created_project.name,
                    description=created_project.description,
                    status=created_project.status,
                    created_at=created_project.created_at,
                )
            )
