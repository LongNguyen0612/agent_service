"""Git Sync Job Repository Interface - UC-31"""
from abc import ABC, abstractmethod
from typing import List, Optional
from src.domain.git_sync_job import GitSyncJob


class IGitSyncJobRepository(ABC):
    """Interface for GitSyncJob repository - UC-31"""

    @abstractmethod
    async def create(self, git_sync_job: GitSyncJob) -> GitSyncJob:
        """Create a new Git sync job"""
        pass

    @abstractmethod
    async def get_by_id(self, job_id: str, tenant_id: str = None) -> Optional[GitSyncJob]:
        """Get Git sync job by ID, optionally filtered by tenant for security"""
        pass

    @abstractmethod
    async def get_by_artifact(self, artifact_id: str, tenant_id: str) -> List[GitSyncJob]:
        """Get all Git sync jobs for an artifact"""
        pass

    @abstractmethod
    async def update(self, git_sync_job: GitSyncJob) -> GitSyncJob:
        """Update an existing Git sync job"""
        pass

    @abstractmethod
    async def get_pending_jobs(self, limit: int = 10) -> List[GitSyncJob]:
        """Get pending Git sync jobs for processing"""
        pass

    @abstractmethod
    async def get_retryable_jobs(self, limit: int = 10) -> List[GitSyncJob]:
        """Get failed jobs that can be retried"""
        pass
