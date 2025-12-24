"""Sync To Git Use Case - UC-31

Creates a new async job to sync an artifact to a Git repository.
"""
from libs.result import Result, Error, Return
from src.app.services.unit_of_work import UnitOfWork
from src.domain.git_sync_job import GitSyncJob
from src.domain.enums import ArtifactStatus
from .dtos import SyncToGitRequestDTO, SyncToGitResponseDTO


class SyncToGitUseCase:
    """
    Use case: Sync Artifact to Git (UC-31)

    Creates an async job to push an approved artifact to a Git repository.
    Only approved artifacts can be synced.
    """

    def __init__(self, uow: UnitOfWork, tenant_id: str):
        self.uow = uow
        self.tenant_id = tenant_id

    async def execute(
        self, artifact_id: str, request: SyncToGitRequestDTO
    ) -> Result[SyncToGitResponseDTO]:
        """
        Create a new Git sync job for an artifact

        Args:
            artifact_id: The artifact ID to sync
            request: Git sync configuration (repo URL, branch, commit message)

        Returns:
            Result[SyncToGitResponseDTO]: Sync job ID and status
        """
        async with self.uow:
            # Get artifact and verify ownership
            artifact = await self.uow.artifacts.get_by_id(artifact_id)
            if not artifact:
                return Return.err(
                    Error(code="ARTIFACT_NOT_FOUND", message="Artifact not found")
                )

            # Get the task to verify tenant ownership
            task = await self.uow.tasks.get_by_id(artifact.task_id, self.tenant_id)
            if not task:
                return Return.err(
                    Error(code="ARTIFACT_NOT_FOUND", message="Artifact not found")
                )

            # Only approved artifacts can be synced
            if artifact.status != ArtifactStatus.approved:
                return Return.err(
                    Error(
                        code="ARTIFACT_NOT_APPROVED",
                        message="Only approved artifacts can be synced to Git",
                    )
                )

            # Validate repository URL format
            if not self._validate_repository_url(request.repository_url):
                return Return.err(
                    Error(
                        code="INVALID_REPOSITORY_URL",
                        message="Invalid Git repository URL format",
                    )
                )

            # Create Git sync job
            git_sync_job = GitSyncJob(
                artifact_id=artifact_id,
                tenant_id=self.tenant_id,
                repository_url=request.repository_url,
                branch=request.branch,
                commit_message=request.commit_message,
            )
            git_sync_job = await self.uow.git_sync_jobs.create(git_sync_job)
            await self.uow.commit()

            return Return.ok(
                SyncToGitResponseDTO(
                    sync_job_id=git_sync_job.id,
                    status=(
                        git_sync_job.status.value
                        if hasattr(git_sync_job.status, "value")
                        else git_sync_job.status
                    ),
                )
            )

    def _validate_repository_url(self, url: str) -> bool:
        """Validate Git repository URL format"""
        # Accept HTTPS and SSH URLs
        if url.startswith("https://") and ".git" in url:
            return True
        if url.startswith("https://github.com/"):
            return True
        if url.startswith("https://gitlab.com/"):
            return True
        if url.startswith("https://bitbucket.org/"):
            return True
        if url.startswith("git@"):
            return True
        return False
