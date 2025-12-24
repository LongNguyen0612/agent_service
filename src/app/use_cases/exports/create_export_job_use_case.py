"""Create Export Job Use Case - UC-30

Creates a new async export job for generating a ZIP of project artifacts.
"""
from libs.result import Result, Error, Return
from src.app.services.unit_of_work import UnitOfWork
from src.domain.export_job import ExportJob
from src.domain.enums import ArtifactStatus
from .dtos import CreateExportJobResponseDTO


class CreateExportJobUseCase:
    """
    Use case: Create Export Job (UC-30)

    Creates an async job to export project artifacts as a ZIP file.
    Only exports approved artifacts.
    """

    def __init__(self, uow: UnitOfWork, tenant_id: str):
        self.uow = uow
        self.tenant_id = tenant_id

    async def execute(self, project_id: str) -> Result[CreateExportJobResponseDTO]:
        """
        Create a new export job for a project

        Args:
            project_id: The project ID to export

        Returns:
            Result[CreateExportJobResponseDTO]: Export job ID and status
        """
        async with self.uow:
            # Verify project exists and belongs to tenant
            project = await self.uow.projects.get_by_id(project_id, self.tenant_id)
            if not project:
                return Return.err(Error(
                    code="PROJECT_NOT_FOUND",
                    message="Project not found"
                ))

            # Check if there are any approved artifacts to export
            # Get all tasks for the project first
            tasks = await self.uow.tasks.find_by_project_id(project_id, self.tenant_id)
            if not tasks:
                return Return.err(Error(
                    code="NO_ARTIFACTS",
                    message="No tasks found in project"
                ))

            # Check for approved artifacts across all tasks
            has_approved_artifacts = False
            for task in tasks:
                artifacts = await self.uow.artifacts.get_by_task(task.id)
                for artifact in artifacts:
                    if artifact.status == ArtifactStatus.approved:
                        has_approved_artifacts = True
                        break
                if has_approved_artifacts:
                    break

            if not has_approved_artifacts:
                return Return.err(Error(
                    code="NO_APPROVED_ARTIFACTS",
                    message="No approved artifacts found in project"
                ))

            # Create export job
            export_job = ExportJob(
                project_id=project_id,
                tenant_id=self.tenant_id
            )
            export_job = await self.uow.export_jobs.create(export_job)
            await self.uow.commit()

            return Return.ok(CreateExportJobResponseDTO(
                export_job_id=export_job.id,
                status=export_job.status.value if hasattr(export_job.status, 'value') else export_job.status
            ))
