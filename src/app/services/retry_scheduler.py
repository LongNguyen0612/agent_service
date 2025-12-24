"""Retry Scheduler Service - Story 2.5

Service for scheduling retry jobs with exponential backoff.
"""
from datetime import datetime, timedelta
from src.domain.retry_job import RetryJob
from src.domain.enums import RetryStatus
from src.app.repositories.retry_job_repository import IRetryJobRepository


class RetryScheduler:
    """
    Retry Scheduler Service - AC-2.5.1

    Schedules retry jobs for failed pipeline steps with exponential backoff.
    """

    def __init__(self, retry_job_repository: IRetryJobRepository):
        """
        Initialize RetryScheduler.

        Args:
            retry_job_repository: Repository for managing retry jobs
        """
        self.retry_job_repository = retry_job_repository

    def calculate_backoff(self, retry_count: int) -> int:
        """
        Calculate exponential backoff delay in seconds.

        Formula: 2 ^ retry_count
        Examples: retry_count=0 -> 1s, retry_count=1 -> 2s, retry_count=2 -> 4s

        Args:
            retry_count: Current retry attempt number (0-indexed)

        Returns:
            int: Delay in seconds
        """
        return 2 ** retry_count

    async def schedule_retry(
        self,
        step_run_id: str,
        retry_count: int
    ) -> RetryJob:
        """
        Schedule a retry job for a failed pipeline step.

        Creates a new RetryJob with exponential backoff scheduling.
        The job will be processed by the RetryWorker when scheduled_at is reached.

        Args:
            step_run_id: ID of the failed pipeline step run
            retry_count: Current retry attempt number (0-indexed)

        Returns:
            RetryJob: The created retry job
        """
        # Calculate backoff delay
        delay_seconds = self.calculate_backoff(retry_count)

        # Calculate scheduled time
        now = datetime.utcnow()
        scheduled_at = now + timedelta(seconds=delay_seconds)

        # Create retry job
        retry_job = RetryJob(
            step_run_id=step_run_id,
            retry_attempt=retry_count,
            scheduled_at=scheduled_at,
            status=RetryStatus.pending
        )

        # Persist retry job
        return await self.retry_job_repository.create(retry_job)
