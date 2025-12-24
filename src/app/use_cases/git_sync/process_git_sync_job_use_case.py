"""Process Git Sync Job Use Case - UC-31

Background job processor that executes Git sync operations.
"""
import logging
from libs.result import Result, Error, Return
from src.app.services.unit_of_work import UnitOfWork
from src.app.services.git_service import IGitService
from src.domain.enums import GitSyncJobStatus

logger = logging.getLogger(__name__)


class ProcessGitSyncJobUseCase:
    """
    Use case: Process Git Sync Job (UC-31)

    Background processor that:
    1. Retrieves artifact content
    2. Pushes to Git repository
    3. Updates job status with result
    """

    def __init__(self, uow: UnitOfWork, git_service: IGitService):
        self.uow = uow
        self.git_service = git_service

    async def execute(self, job_id: str) -> Result[bool]:
        """
        Process a Git sync job

        Args:
            job_id: The Git sync job ID to process

        Returns:
            Result[bool]: True if successful
        """
        async with self.uow:
            # Get the job
            job = await self.uow.git_sync_jobs.get_by_id(job_id)
            if not job:
                logger.error(f"[ProcessGitSync] Job not found: {job_id}")
                return Return.err(
                    Error(
                        code="GIT_SYNC_JOB_NOT_FOUND", message="Git sync job not found"
                    )
                )

            # Skip if not pending
            if job.status != GitSyncJobStatus.pending:
                logger.info(
                    f"[ProcessGitSync] Job {job_id} is not pending, status: {job.status}"
                )
                return Return.ok(False)

            # Mark as processing
            job.start_processing()
            await self.uow.git_sync_jobs.update(job)
            await self.uow.commit()

        # Get artifact content (new transaction)
        async with self.uow:
            artifact = await self.uow.artifacts.get_by_id(job.artifact_id)
            if not artifact:
                job.fail("Artifact not found")
                await self.uow.git_sync_jobs.update(job)
                await self.uow.commit()
                return Return.err(
                    Error(code="ARTIFACT_NOT_FOUND", message="Artifact not found")
                )

            # Get artifact content
            content = self._get_artifact_content(artifact)
            if not content:
                job.fail("Artifact has no content")
                await self.uow.git_sync_jobs.update(job)
                await self.uow.commit()
                return Return.err(
                    Error(code="NO_CONTENT", message="Artifact has no content")
                )

            # Determine file path based on artifact type
            file_path = self._get_file_path(artifact)

            logger.info(
                f"[ProcessGitSync] Pushing artifact {artifact.id} to "
                f"{job.repository_url}:{job.branch}/{file_path}"
            )

            # Push to Git
            result = await self.git_service.push_content(
                repository_url=job.repository_url,
                branch=job.branch,
                file_path=file_path,
                content=content,
                commit_message=job.commit_message,
            )

            if result.success:
                job.complete(result.commit_sha)
                logger.info(
                    f"[ProcessGitSync] Successfully pushed to Git. "
                    f"Commit SHA: {result.commit_sha}"
                )
            else:
                job.fail(result.error_message or "Unknown error")
                logger.error(
                    f"[ProcessGitSync] Failed to push to Git: {result.error_message}"
                )

                # Schedule retry if possible
                if job.can_retry():
                    job.increment_retry()
                    logger.info(
                        f"[ProcessGitSync] Job scheduled for retry. "
                        f"Attempt {job.retry_count}/{job.max_retries}"
                    )

            await self.uow.git_sync_jobs.update(job)
            await self.uow.commit()

            return Return.ok(result.success)

    def _get_artifact_content(self, artifact) -> str:
        """Extract content from artifact"""
        if artifact.content:
            # If content is a dict, convert to string
            if isinstance(artifact.content, dict):
                import json

                return json.dumps(artifact.content, indent=2)
            return str(artifact.content)
        return ""

    def _get_file_path(self, artifact) -> str:
        """Determine file path based on artifact type"""
        from src.domain.enums import ArtifactType

        # Map artifact types to file extensions
        type_mapping = {
            ArtifactType.CODE_FILES: f"generated/{artifact.id}.py",
            ArtifactType.code: f"generated/{artifact.id}.py",
            ArtifactType.USER_STORIES: f"docs/{artifact.id}.md",
            ArtifactType.ANALYSIS_REPORT: f"docs/{artifact.id}.md",
            ArtifactType.document: f"docs/{artifact.id}.md",
            ArtifactType.TEST_SUITE: f"tests/{artifact.id}.py",
        }

        artifact_type = artifact.artifact_type
        if hasattr(artifact_type, "value"):
            artifact_type = ArtifactType(artifact_type)

        return type_mapping.get(artifact_type, f"artifacts/{artifact.id}.txt")
