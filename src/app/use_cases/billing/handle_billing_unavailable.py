"""Handle Billing Unavailable Use Case - UC-51

Handles temporary unavailability of the Billing service during AI execution.
Creates RetryJob for billing retry with exponential backoff.
"""

import logging
from datetime import datetime, timedelta
from libs.result import Result, Return, Error
from src.app.repositories.retry_job_repository import IRetryJobRepository
from src.app.services.audit_service import AuditService
from src.app.services.unit_of_work import UnitOfWork
from src.domain.retry_job import RetryJob
from src.domain.enums import RetryStatus
from .dtos import BillingUnavailableCommandDTO, BillingUnavailableResponseDTO

logger = logging.getLogger(__name__)


class HandleBillingUnavailable:
    """
    Use case for handling billing service unavailability - UC-51

    When billing service is temporarily unavailable during credit consumption,
    this use case:
    1. Creates a RetryJob with exponential backoff scheduling
    2. Logs audit event for the billing unavailability
    3. Returns retry job details for pipeline step pause coordination

    This prevents duplicate credit consumption by using idempotency keys
    and ensures billing operations are eventually completed.
    """

    # Retry configuration
    DEFAULT_MAX_RETRIES = 5
    DEFAULT_BASE_DELAY_SECONDS = 60

    def __init__(
        self,
        retry_job_repository: IRetryJobRepository,
        audit_service: AuditService,
        uow: UnitOfWork,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay_seconds: int = DEFAULT_BASE_DELAY_SECONDS,
    ):
        """
        Initialize HandleBillingUnavailable use case.

        Args:
            retry_job_repository: Repository for managing retry jobs
            audit_service: Service for logging audit events
            uow: Unit of work for transaction management
            max_retries: Maximum number of retry attempts (default: 5)
            base_delay_seconds: Base delay for exponential backoff (default: 60s)
        """
        self.retry_job_repository = retry_job_repository
        self.audit_service = audit_service
        self.uow = uow
        self.max_retries = max_retries
        self.base_delay_seconds = base_delay_seconds

    def _calculate_backoff_delay(self, retry_attempt: int) -> int:
        """
        Calculate exponential backoff delay in seconds.

        Formula: base_delay_seconds * (2 ^ retry_attempt)

        Args:
            retry_attempt: Current retry attempt number (0-indexed)

        Returns:
            int: Delay in seconds before next retry
        """
        return self.base_delay_seconds * (2**retry_attempt)

    async def execute(
        self, command: BillingUnavailableCommandDTO
    ) -> Result[BillingUnavailableResponseDTO]:
        """
        Handle billing service unavailability by creating a retry job.

        Flow:
        1. Validate retry attempt is within allowed limit
        2. Calculate exponential backoff for scheduled_at
        3. Create RetryJob entity
        4. Persist RetryJob via repository
        5. Log audit event (billing_unavailable)
        6. Commit transaction
        7. Return Result[BillingUnavailableResponseDTO]

        Args:
            command: Command with billing failure context

        Returns:
            Result[BillingUnavailableResponseDTO]: Retry job details or error
        """
        # Step 1: Validate retry attempt limit
        if command.retry_attempt >= self.max_retries:
            logger.error(
                f"Max retries ({self.max_retries}) exceeded for step_run_id={command.step_run_id}"
            )
            return Return.err(
                Error(
                    code="MAX_RETRIES_EXCEEDED",
                    message=f"Maximum retry attempts ({self.max_retries}) exceeded for billing operation",
                    reason=f"step_run_id={command.step_run_id}, attempt={command.retry_attempt}",
                )
            )

        # Step 2: Calculate exponential backoff
        delay_seconds = self._calculate_backoff_delay(command.retry_attempt)
        scheduled_at = datetime.utcnow() + timedelta(seconds=delay_seconds)

        logger.info(
            f"Scheduling billing retry for step_run_id={command.step_run_id}, "
            f"attempt={command.retry_attempt + 1}, scheduled_at={scheduled_at}"
        )

        # Step 3: Create RetryJob entity
        retry_job = RetryJob(
            step_run_id=command.step_run_id,
            retry_attempt=command.retry_attempt + 1,
            scheduled_at=scheduled_at,
            status=RetryStatus.pending,
        )

        try:
            # Step 4: Persist RetryJob
            created_job = await self.retry_job_repository.create(retry_job)

            # Step 5: Log audit event
            await self.audit_service.log_event(
                event_type="billing_unavailable",
                tenant_id=command.tenant_id,
                user_id="system",
                resource_type="retry_job",
                resource_id=created_job.id,
                metadata={
                    "step_run_id": command.step_run_id,
                    "amount": str(command.amount),
                    "idempotency_key": command.idempotency_key,
                    "retry_attempt": command.retry_attempt + 1,
                    "scheduled_at": scheduled_at.isoformat(),
                    "delay_seconds": delay_seconds,
                    "error_message": command.error_message,
                },
            )

            # Step 6: Commit transaction
            await self.uow.commit()

            logger.info(
                f"Created retry job {created_job.id} for billing retry, "
                f"scheduled_at={scheduled_at}"
            )

            # Step 7: Return response
            return Return.ok(
                BillingUnavailableResponseDTO(
                    retry_job_id=created_job.id,
                    scheduled_at=scheduled_at,
                    message=f"Billing retry scheduled for {scheduled_at.isoformat()}",
                    retry_attempt=command.retry_attempt + 1,
                )
            )

        except Exception as e:
            logger.error(f"Failed to create retry job for step_run_id={command.step_run_id}: {e}")
            await self.uow.rollback()
            return Return.err(
                Error(
                    code="RETRY_JOB_CREATION_FAILED",
                    message="Failed to schedule billing retry",
                    reason=str(e),
                )
            )
