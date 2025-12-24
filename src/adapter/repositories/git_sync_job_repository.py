"""SQLAlchemy Git Sync Job Repository - UC-31"""
from typing import List, Optional
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from src.app.repositories.git_sync_job_repository import IGitSyncJobRepository
from src.domain.git_sync_job import GitSyncJob
from src.domain.enums import GitSyncJobStatus


class SqlAlchemyGitSyncJobRepository(IGitSyncJobRepository):
    """SQLAlchemy implementation of GitSyncJob repository - UC-31"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, git_sync_job: GitSyncJob) -> GitSyncJob:
        """Create a new Git sync job"""
        self.session.add(git_sync_job)
        await self.session.flush()
        await self.session.refresh(git_sync_job)
        return git_sync_job

    async def get_by_id(self, job_id: str, tenant_id: str = None) -> Optional[GitSyncJob]:
        """Get Git sync job by ID, optionally filtered by tenant for security"""
        stmt = select(GitSyncJob).where(GitSyncJob.id == job_id)
        if tenant_id:
            stmt = stmt.where(GitSyncJob.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_artifact(self, artifact_id: str, tenant_id: str) -> List[GitSyncJob]:
        """Get all Git sync jobs for an artifact"""
        stmt = (
            select(GitSyncJob)
            .where(GitSyncJob.artifact_id == artifact_id, GitSyncJob.tenant_id == tenant_id)
            .order_by(GitSyncJob.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, git_sync_job: GitSyncJob) -> GitSyncJob:
        """Update an existing Git sync job"""
        self.session.add(git_sync_job)
        await self.session.flush()
        await self.session.refresh(git_sync_job)
        return git_sync_job

    async def get_pending_jobs(self, limit: int = 10) -> List[GitSyncJob]:
        """Get pending Git sync jobs for processing"""
        stmt = (
            select(GitSyncJob)
            .where(GitSyncJob.status == GitSyncJobStatus.pending)
            .order_by(GitSyncJob.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_retryable_jobs(self, limit: int = 10) -> List[GitSyncJob]:
        """Get failed jobs that can be retried"""
        stmt = (
            select(GitSyncJob)
            .where(
                GitSyncJob.status == GitSyncJobStatus.failed,
                GitSyncJob.retry_count < GitSyncJob.max_retries,
            )
            .order_by(GitSyncJob.completed_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
