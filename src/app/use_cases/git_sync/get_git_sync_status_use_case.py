"""Get Git Sync Status Use Case - UC-31

Retrieves the status of a Git sync job.
"""
from libs.result import Result, Error, Return
from src.app.services.unit_of_work import UnitOfWork
from .dtos import GitSyncStatusDTO


class GetGitSyncStatusUseCase:
    """
    Use case: Get Git Sync Job Status (UC-31)

    Returns the current status of a Git sync job.
    When complete, includes the commit SHA.
    """

    def __init__(self, uow: UnitOfWork, tenant_id: str):
        self.uow = uow
        self.tenant_id = tenant_id

    async def execute(self, job_id: str) -> Result[GitSyncStatusDTO]:
        """
        Get Git sync job status

        Args:
            job_id: The Git sync job ID

        Returns:
            Result[GitSyncStatusDTO]: Job status details
        """
        async with self.uow:
            # Get job with tenant filter for security
            job = await self.uow.git_sync_jobs.get_by_id(job_id, self.tenant_id)
            if not job:
                return Return.err(
                    Error(
                        code="GIT_SYNC_JOB_NOT_FOUND", message="Git sync job not found"
                    )
                )

            return Return.ok(
                GitSyncStatusDTO(
                    id=job.id,
                    artifact_id=job.artifact_id,
                    repository_url=job.repository_url,
                    branch=job.branch,
                    status=(
                        job.status.value if hasattr(job.status, "value") else job.status
                    ),
                    commit_sha=job.commit_sha,
                    error_message=job.error_message,
                    retry_count=job.retry_count,
                    created_at=job.created_at,
                    started_at=job.started_at,
                    completed_at=job.completed_at,
                )
            )
