"""Retry Job Repository Interface - Story 2.5

Interface for managing RetryJob entities (retry scheduling and processing).
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from src.domain.retry_job import RetryJob
from src.domain.enums import RetryStatus


class IRetryJobRepository(ABC):
    """Interface for RetryJob repository - AC-2.5.2"""

    @abstractmethod
    async def create(self, retry_job: RetryJob) -> RetryJob:
        """
        Create a new retry job record.

        Args:
            retry_job: RetryJob entity to create

        Returns:
            RetryJob: Created retry job with generated ID
        """
        pass

    @abstractmethod
    async def get_by_id(self, job_id: str) -> Optional[RetryJob]:
        """
        Get retry job by ID.

        Args:
            job_id: ID of the retry job

        Returns:
            Optional[RetryJob]: Retry job if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_due_jobs(self) -> List[RetryJob]:
        """
        Get all retry jobs that are ready to be processed.
        Returns jobs where scheduled_at <= now AND status = pending.

        Returns:
            List[RetryJob]: List of due retry jobs, ordered by scheduled_at
        """
        pass

    @abstractmethod
    async def update_status(self, job_id: str, status: RetryStatus) -> None:
        """
        Update the status of a retry job.

        Args:
            job_id: ID of the retry job
            status: New status to set
        """
        pass

    @abstractmethod
    async def get_by_step_run_id(self, step_run_id: str) -> List[RetryJob]:
        """
        Get all retry jobs for a specific step run.

        Args:
            step_run_id: ID of the pipeline step run

        Returns:
            List[RetryJob]: List of retry jobs for the step run
        """
        pass
