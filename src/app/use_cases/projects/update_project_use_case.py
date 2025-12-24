from libs.result import Result, Error, Return
from src.app.services.unit_of_work import UnitOfWork
from src.app.services.audit_service import AuditService
from src.app.repositories import ProjectRepository
from src.adapter.repositories import SqlAlchemyProjectRepository
from .dtos import UpdateProjectCommand, UpdateProjectResponse


class UpdateProjectUseCase:
    """Use case for updating an existing project"""

    def __init__(self, uow: UnitOfWork, audit_service: AuditService):
        self.uow = uow
        self.audit_service = audit_service

    async def execute(self, command: UpdateProjectCommand) -> Result[UpdateProjectResponse]:
        """
        Execute the update project use case

        Returns:
            Result[UpdateProjectResponse]: Success with updated project data or error
        """
        async with self.uow as session:
            # Create repository
            project_repo: ProjectRepository = SqlAlchemyProjectRepository(session.session)

            # Get existing project with tenant isolation
            project = await project_repo.get_by_id(command.project_id, command.tenant_id)

            # AC-1.2.3: Project Not Found
            if project is None:
                return Return.err(
                    Error(code="NOT_FOUND", message=f"Project {command.project_id} not found")
                )

            # TODO: AC-1.2.2: Permission Check
            # Once we have full auth context with user role, add permission validation here:
            # if user_role not in ['admin', 'owner']:
            #     return Return.err(Error(code="INSUFFICIENT_PERMISSIONS", message="..."))

            # Update fields if provided
            if command.name is not None:
                if len(command.name.strip()) == 0:
                    return Return.err(
                        Error(code="INVALID_INPUT", message="Project name cannot be empty")
                    )
                project.name = command.name.strip()

            if command.description is not None:
                project.description = command.description

            if command.status is not None:
                project.status = command.status

            # Persist changes
            updated_project = await project_repo.update(project)
            await self.uow.commit()

            # AC-1.2.4: Audit Logging
            await self.audit_service.log_event(
                event_type="project_updated",
                tenant_id=command.tenant_id,
                user_id=command.user_id,
                resource_type="project",
                resource_id=updated_project.id,
                metadata={
                    "project_name": updated_project.name,
                    "updated_fields": {
                        "name": command.name is not None,
                        "description": command.description is not None,
                        "status": command.status is not None,
                    },
                },
            )

            # Return response DTO
            return Return.ok(
                UpdateProjectResponse(
                    id=updated_project.id,
                    tenant_id=updated_project.tenant_id,
                    name=updated_project.name,
                    description=updated_project.description,
                    status=updated_project.status,
                    created_at=updated_project.created_at,
                )
            )
