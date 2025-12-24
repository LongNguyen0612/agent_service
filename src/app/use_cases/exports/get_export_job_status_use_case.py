"""Get Export Job Status Use Case - UC-30

Retrieves the status of an export job including download URL if complete.
"""
from libs.result import Result, Error, Return
from src.app.services.unit_of_work import UnitOfWork
from .dtos import ExportJobStatusDTO


class GetExportJobStatusUseCase:
    """
    Use case: Get Export Job Status (UC-30)

    Returns the current status of an export job, including download URL
    when the job is completed.
    """

    def __init__(self, uow: UnitOfWork, tenant_id: str):
        self.uow = uow
        self.tenant_id = tenant_id

    async def execute(self, job_id: str) -> Result[ExportJobStatusDTO]:
        """
        Get the status of an export job

        Args:
            job_id: The export job ID

        Returns:
            Result[ExportJobStatusDTO]: Job status with download URL if complete
        """
        async with self.uow:
            # Get export job with tenant isolation
            export_job = await self.uow.export_jobs.get_by_id(job_id, self.tenant_id)
            if not export_job:
                return Return.err(Error(
                    code="EXPORT_JOB_NOT_FOUND",
                    message="Export job not found"
                ))

            return Return.ok(ExportJobStatusDTO(
                export_job_id=export_job.id,
                project_id=export_job.project_id,
                status=export_job.status.value if hasattr(export_job.status, 'value') else export_job.status,
                download_url=export_job.download_url,
                expires_at=export_job.expires_at,
                error_message=export_job.error_message,
                created_at=export_job.created_at,
                started_at=export_job.started_at,
                completed_at=export_job.completed_at
            ))
