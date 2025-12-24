"""Retry Job Repository Implementation - Story 2.5

SQLAlchemy implementation for managing RetryJob entities.
"""
from datetime import datetime
from typing import List, Optional
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from src.app.repositories.retry_job_repository import IRetryJobRepository
from src.domain.retry_job import RetryJob
from src.domain.enums import RetryStatus


class RetryJobRepository(IRetryJobRepository):
    """SQLAlchemy implementation of Retry Job repository - Story 2.5, AC-2.5.2"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, retry_job: RetryJob) -> RetryJob:
        """
        Create a new retry job record.

        Args:
            retry_job: RetryJob entity to create

        Returns:
            RetryJob: Created retry job with generated ID
        """
        self.session.add(retry_job)
        await self.session.flush()
        await self.session.refresh(retry_job)
        return retry_job

    async def get_by_id(self, job_id: str) -> Optional[RetryJob]:
        """
        Get retry job by ID.

        Args:
            job_id: ID of the retry job

        Returns:
            Optional[RetryJob]: Retry job if found, None otherwise
        """
        stmt = select(RetryJob).where(RetryJob.id == job_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_due_jobs(self) -> List[RetryJob]:
        """
        Get all retry jobs that are ready to be processed.
        Returns jobs where scheduled_at <= now AND status = pending.

        Returns:
            List[RetryJob]: List of due retry jobs, ordered by scheduled_at
        """
        now = datetime.utcnow()
        stmt = (
            select(RetryJob)
            .where(
                RetryJob.status == RetryStatus.pending,
                RetryJob.scheduled_at <= now
            )
            .order_by(RetryJob.scheduled_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(self, job_id: str, status: RetryStatus) -> None:
        """
        Update the status of a retry job.

        Args:
            job_id: ID of the retry job
            status: New status to set
        """
        retry_job = await self.get_by_id(job_id)
        if retry_job:
            retry_job.status = status
            if status in (RetryStatus.completed, RetryStatus.failed):
                retry_job.processed_at = datetime.utcnow()
            await self.session.flush()

    async def get_by_step_run_id(self, step_run_id: str) -> List[RetryJob]:
        """
        Get all retry jobs for a specific step run.

        Args:
            step_run_id: ID of the pipeline step run

        Returns:
            List[RetryJob]: List of retry jobs for the step run
        """
        stmt = (
            select(RetryJob)
            .where(RetryJob.step_run_id == step_run_id)
            .order_by(RetryJob.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
