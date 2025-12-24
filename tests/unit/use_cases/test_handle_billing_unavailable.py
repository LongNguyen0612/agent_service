"""Unit tests for HandleBillingUnavailable use case - UC-51

Tests for handling billing service unavailability during AI execution.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from decimal import Decimal

from src.app.use_cases.billing.handle_billing_unavailable import HandleBillingUnavailable
from src.app.use_cases.billing.dtos import (
    BillingUnavailableCommandDTO,
    BillingUnavailableResponseDTO,
)
from src.domain.retry_job import RetryJob
from src.domain.enums import RetryStatus


@pytest.fixture
def mock_retry_job_repository():
    repo = MagicMock()
    repo.create = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.get_by_step_run_id = AsyncMock()
    return repo


@pytest.fixture
def mock_audit_service():
    service = MagicMock()
    service.log_event = AsyncMock()
    return service


@pytest.fixture
def mock_uow():
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock()
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    return uow


@pytest.fixture
def use_case(mock_retry_job_repository, mock_audit_service, mock_uow):
    return HandleBillingUnavailable(
        retry_job_repository=mock_retry_job_repository,
        audit_service=mock_audit_service,
        uow=mock_uow,
    )


@pytest.fixture
def sample_command():
    return BillingUnavailableCommandDTO(
        step_run_id="step_run_123",
        tenant_id="tenant_456",
        amount=Decimal("10.50"),
        idempotency_key="billing:step_run_123:attempt_0",
        retry_attempt=0,
        error_message="Connection timeout to billing service",
    )


@pytest.mark.asyncio
class TestHandleBillingUnavailable:
    """Test suite for HandleBillingUnavailable use case - UC-51"""

    async def test_create_retry_job_first_attempt_success(
        self,
        use_case,
        mock_retry_job_repository,
        mock_audit_service,
        mock_uow,
        sample_command,
    ):
        """Test AT-51.1: Successfully create retry job on first billing failure"""
        # Arrange
        created_job = RetryJob(
            id="retry_job_001",
            step_run_id=sample_command.step_run_id,
            retry_attempt=1,
            scheduled_at=datetime.utcnow() + timedelta(seconds=60),
            status=RetryStatus.pending,
        )
        mock_retry_job_repository.create.return_value = created_job

        # Act
        result = await use_case.execute(sample_command)

        # Assert
        assert result.is_ok()
        dto = result.value
        assert dto.retry_job_id == "retry_job_001"
        assert dto.retry_attempt == 1
        assert dto.scheduled_at is not None
        assert "scheduled" in dto.message.lower()

        # Verify repository was called with correct retry job
        mock_retry_job_repository.create.assert_called_once()
        created_retry_job = mock_retry_job_repository.create.call_args[0][0]
        assert created_retry_job.step_run_id == sample_command.step_run_id
        assert created_retry_job.retry_attempt == 1
        assert created_retry_job.status == RetryStatus.pending

        # Verify audit event was logged
        mock_audit_service.log_event.assert_called_once()
        audit_call = mock_audit_service.log_event.call_args
        assert audit_call.kwargs["event_type"] == "billing_unavailable"
        assert audit_call.kwargs["tenant_id"] == sample_command.tenant_id
        assert audit_call.kwargs["resource_type"] == "retry_job"
        assert audit_call.kwargs["resource_id"] == "retry_job_001"

        # Verify commit was called
        mock_uow.commit.assert_called_once()

    async def test_exponential_backoff_calculation_first_attempt(
        self,
        use_case,
        mock_retry_job_repository,
        mock_audit_service,
        mock_uow,
    ):
        """Test exponential backoff: first attempt = base_delay * 2^0 = 60 seconds"""
        # Arrange
        command = BillingUnavailableCommandDTO(
            step_run_id="step_123",
            tenant_id="tenant_123",
            amount=Decimal("5.00"),
            idempotency_key="key_123",
            retry_attempt=0,
        )

        created_job = RetryJob(
            id="job_001",
            step_run_id="step_123",
            retry_attempt=1,
            scheduled_at=datetime.utcnow() + timedelta(seconds=60),
            status=RetryStatus.pending,
        )
        mock_retry_job_repository.create.return_value = created_job

        # Act
        with patch("src.app.use_cases.billing.handle_billing_unavailable.datetime") as mock_dt:
            mock_now = datetime(2024, 1, 1, 12, 0, 0)
            mock_dt.utcnow.return_value = mock_now
            result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        # Verify the scheduled_at is 60 seconds from now (base_delay * 2^0)
        created_retry_job = mock_retry_job_repository.create.call_args[0][0]
        expected_scheduled_at = mock_now + timedelta(seconds=60)
        assert created_retry_job.scheduled_at == expected_scheduled_at

    async def test_exponential_backoff_calculation_third_attempt(
        self,
        mock_retry_job_repository,
        mock_audit_service,
        mock_uow,
    ):
        """Test exponential backoff: third attempt = base_delay * 2^2 = 240 seconds"""
        # Arrange
        use_case = HandleBillingUnavailable(
            retry_job_repository=mock_retry_job_repository,
            audit_service=mock_audit_service,
            uow=mock_uow,
            base_delay_seconds=60,
        )

        command = BillingUnavailableCommandDTO(
            step_run_id="step_123",
            tenant_id="tenant_123",
            amount=Decimal("5.00"),
            idempotency_key="key_123",
            retry_attempt=2,  # Third attempt (0-indexed)
        )

        created_job = RetryJob(
            id="job_001",
            step_run_id="step_123",
            retry_attempt=3,
            scheduled_at=datetime.utcnow() + timedelta(seconds=240),
            status=RetryStatus.pending,
        )
        mock_retry_job_repository.create.return_value = created_job

        # Act
        with patch("src.app.use_cases.billing.handle_billing_unavailable.datetime") as mock_dt:
            mock_now = datetime(2024, 1, 1, 12, 0, 0)
            mock_dt.utcnow.return_value = mock_now
            result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        created_retry_job = mock_retry_job_repository.create.call_args[0][0]
        # 60 * 2^2 = 240 seconds
        expected_scheduled_at = mock_now + timedelta(seconds=240)
        assert created_retry_job.scheduled_at == expected_scheduled_at

    async def test_max_retries_exceeded_returns_error(
        self,
        use_case,
        mock_retry_job_repository,
        mock_audit_service,
        mock_uow,
    ):
        """Test that exceeding max retries returns an error"""
        # Arrange
        command = BillingUnavailableCommandDTO(
            step_run_id="step_123",
            tenant_id="tenant_123",
            amount=Decimal("5.00"),
            idempotency_key="key_123",
            retry_attempt=5,  # Max retries is 5, so this is 6th attempt
        )

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_err()
        error = result.error
        assert error.code == "MAX_RETRIES_EXCEEDED"
        assert "5" in error.message  # Should mention max retries

        # Verify no retry job was created
        mock_retry_job_repository.create.assert_not_called()
        mock_audit_service.log_event.assert_not_called()
        mock_uow.commit.assert_not_called()

    async def test_custom_max_retries_configuration(
        self,
        mock_retry_job_repository,
        mock_audit_service,
        mock_uow,
    ):
        """Test custom max_retries configuration"""
        # Arrange
        use_case = HandleBillingUnavailable(
            retry_job_repository=mock_retry_job_repository,
            audit_service=mock_audit_service,
            uow=mock_uow,
            max_retries=3,  # Custom max retries
        )

        command = BillingUnavailableCommandDTO(
            step_run_id="step_123",
            tenant_id="tenant_123",
            amount=Decimal("5.00"),
            idempotency_key="key_123",
            retry_attempt=3,  # 4th attempt with max=3
        )

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_err()
        assert result.error.code == "MAX_RETRIES_EXCEEDED"
        assert "3" in result.error.message

    async def test_custom_base_delay_configuration(
        self,
        mock_retry_job_repository,
        mock_audit_service,
        mock_uow,
    ):
        """Test custom base_delay_seconds configuration"""
        # Arrange
        use_case = HandleBillingUnavailable(
            retry_job_repository=mock_retry_job_repository,
            audit_service=mock_audit_service,
            uow=mock_uow,
            base_delay_seconds=30,  # Custom base delay
        )

        command = BillingUnavailableCommandDTO(
            step_run_id="step_123",
            tenant_id="tenant_123",
            amount=Decimal("5.00"),
            idempotency_key="key_123",
            retry_attempt=0,
        )

        created_job = RetryJob(
            id="job_001",
            step_run_id="step_123",
            retry_attempt=1,
            scheduled_at=datetime.utcnow() + timedelta(seconds=30),
            status=RetryStatus.pending,
        )
        mock_retry_job_repository.create.return_value = created_job

        # Act
        with patch("src.app.use_cases.billing.handle_billing_unavailable.datetime") as mock_dt:
            mock_now = datetime(2024, 1, 1, 12, 0, 0)
            mock_dt.utcnow.return_value = mock_now
            result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        created_retry_job = mock_retry_job_repository.create.call_args[0][0]
        # Custom delay: 30 * 2^0 = 30 seconds
        expected_scheduled_at = mock_now + timedelta(seconds=30)
        assert created_retry_job.scheduled_at == expected_scheduled_at

    async def test_audit_event_contains_all_required_metadata(
        self,
        use_case,
        mock_retry_job_repository,
        mock_audit_service,
        mock_uow,
        sample_command,
    ):
        """Test that audit event contains all required metadata"""
        # Arrange
        created_job = RetryJob(
            id="retry_job_001",
            step_run_id=sample_command.step_run_id,
            retry_attempt=1,
            scheduled_at=datetime.utcnow() + timedelta(seconds=60),
            status=RetryStatus.pending,
        )
        mock_retry_job_repository.create.return_value = created_job

        # Act
        await use_case.execute(sample_command)

        # Assert
        mock_audit_service.log_event.assert_called_once()
        call_kwargs = mock_audit_service.log_event.call_args.kwargs
        metadata = call_kwargs["metadata"]

        assert metadata["step_run_id"] == sample_command.step_run_id
        assert metadata["amount"] == str(sample_command.amount)
        assert metadata["idempotency_key"] == sample_command.idempotency_key
        assert metadata["retry_attempt"] == 1
        assert "scheduled_at" in metadata
        assert metadata["delay_seconds"] == 60
        assert metadata["error_message"] == sample_command.error_message

    async def test_repository_creation_failure_returns_error(
        self,
        use_case,
        mock_retry_job_repository,
        mock_audit_service,
        mock_uow,
        sample_command,
    ):
        """Test that repository creation failure returns error and rolls back"""
        # Arrange
        mock_retry_job_repository.create.side_effect = Exception("Database connection failed")

        # Act
        result = await use_case.execute(sample_command)

        # Assert
        assert result.is_err()
        error = result.error
        assert error.code == "RETRY_JOB_CREATION_FAILED"
        assert "Database connection failed" in error.reason

        # Verify rollback was called
        mock_uow.rollback.assert_called_once()
        mock_uow.commit.assert_not_called()

    async def test_retry_job_created_with_pending_status(
        self,
        use_case,
        mock_retry_job_repository,
        mock_audit_service,
        mock_uow,
        sample_command,
    ):
        """Test that retry job is created with pending status"""
        # Arrange
        created_job = RetryJob(
            id="retry_job_001",
            step_run_id=sample_command.step_run_id,
            retry_attempt=1,
            scheduled_at=datetime.utcnow() + timedelta(seconds=60),
            status=RetryStatus.pending,
        )
        mock_retry_job_repository.create.return_value = created_job

        # Act
        await use_case.execute(sample_command)

        # Assert
        created_retry_job = mock_retry_job_repository.create.call_args[0][0]
        assert created_retry_job.status == RetryStatus.pending

    async def test_retry_attempt_incremented_in_response(
        self,
        use_case,
        mock_retry_job_repository,
        mock_audit_service,
        mock_uow,
    ):
        """Test that retry attempt is incremented by 1 in response"""
        # Arrange
        command = BillingUnavailableCommandDTO(
            step_run_id="step_123",
            tenant_id="tenant_123",
            amount=Decimal("5.00"),
            idempotency_key="key_123",
            retry_attempt=2,  # Input is 2
        )

        created_job = RetryJob(
            id="job_001",
            step_run_id="step_123",
            retry_attempt=3,
            scheduled_at=datetime.utcnow() + timedelta(seconds=240),
            status=RetryStatus.pending,
        )
        mock_retry_job_repository.create.return_value = created_job

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        assert result.value.retry_attempt == 3  # Should be incremented to 3

    async def test_no_error_message_in_command(
        self,
        use_case,
        mock_retry_job_repository,
        mock_audit_service,
        mock_uow,
    ):
        """Test handling when error_message is not provided"""
        # Arrange
        command = BillingUnavailableCommandDTO(
            step_run_id="step_123",
            tenant_id="tenant_123",
            amount=Decimal("5.00"),
            idempotency_key="key_123",
            retry_attempt=0,
            # error_message not provided
        )

        created_job = RetryJob(
            id="job_001",
            step_run_id="step_123",
            retry_attempt=1,
            scheduled_at=datetime.utcnow() + timedelta(seconds=60),
            status=RetryStatus.pending,
        )
        mock_retry_job_repository.create.return_value = created_job

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        metadata = mock_audit_service.log_event.call_args.kwargs["metadata"]
        assert metadata["error_message"] is None

    async def test_backoff_calculation_internal_method(self, use_case):
        """Test _calculate_backoff_delay method directly"""
        # Test various retry attempts
        assert use_case._calculate_backoff_delay(0) == 60  # 60 * 2^0 = 60
        assert use_case._calculate_backoff_delay(1) == 120  # 60 * 2^1 = 120
        assert use_case._calculate_backoff_delay(2) == 240  # 60 * 2^2 = 240
        assert use_case._calculate_backoff_delay(3) == 480  # 60 * 2^3 = 480
        assert use_case._calculate_backoff_delay(4) == 960  # 60 * 2^4 = 960

    async def test_default_configuration_values(self):
        """Test default configuration values"""
        assert HandleBillingUnavailable.DEFAULT_MAX_RETRIES == 5
        assert HandleBillingUnavailable.DEFAULT_BASE_DELAY_SECONDS == 60

    async def test_response_dto_structure(
        self,
        use_case,
        mock_retry_job_repository,
        mock_audit_service,
        mock_uow,
        sample_command,
    ):
        """Test that response DTO has correct structure"""
        # Arrange
        scheduled_at = datetime.utcnow() + timedelta(seconds=60)
        created_job = RetryJob(
            id="retry_job_001",
            step_run_id=sample_command.step_run_id,
            retry_attempt=1,
            scheduled_at=scheduled_at,
            status=RetryStatus.pending,
        )
        mock_retry_job_repository.create.return_value = created_job

        # Act
        result = await use_case.execute(sample_command)

        # Assert
        assert result.is_ok()
        dto = result.value
        assert isinstance(dto, BillingUnavailableResponseDTO)
        assert hasattr(dto, "retry_job_id")
        assert hasattr(dto, "scheduled_at")
        assert hasattr(dto, "message")
        assert hasattr(dto, "retry_attempt")

    async def test_audit_service_failure_does_not_rollback(
        self,
        use_case,
        mock_retry_job_repository,
        mock_audit_service,
        mock_uow,
        sample_command,
    ):
        """Test that audit service failure causes rollback"""
        # Arrange
        created_job = RetryJob(
            id="retry_job_001",
            step_run_id=sample_command.step_run_id,
            retry_attempt=1,
            scheduled_at=datetime.utcnow() + timedelta(seconds=60),
            status=RetryStatus.pending,
        )
        mock_retry_job_repository.create.return_value = created_job
        mock_audit_service.log_event.side_effect = Exception("Audit service unavailable")

        # Act
        result = await use_case.execute(sample_command)

        # Assert
        assert result.is_err()
        assert result.error.code == "RETRY_JOB_CREATION_FAILED"
        mock_uow.rollback.assert_called_once()

    async def test_idempotency_key_preserved_in_metadata(
        self,
        use_case,
        mock_retry_job_repository,
        mock_audit_service,
        mock_uow,
    ):
        """Test that idempotency key is preserved for duplicate prevention"""
        # Arrange
        idempotency_key = "billing:step_123:pipeline_456:unique_id"
        command = BillingUnavailableCommandDTO(
            step_run_id="step_123",
            tenant_id="tenant_123",
            amount=Decimal("5.00"),
            idempotency_key=idempotency_key,
            retry_attempt=0,
        )

        created_job = RetryJob(
            id="job_001",
            step_run_id="step_123",
            retry_attempt=1,
            scheduled_at=datetime.utcnow() + timedelta(seconds=60),
            status=RetryStatus.pending,
        )
        mock_retry_job_repository.create.return_value = created_job

        # Act
        await use_case.execute(command)

        # Assert
        metadata = mock_audit_service.log_event.call_args.kwargs["metadata"]
        assert metadata["idempotency_key"] == idempotency_key


@pytest.mark.asyncio
class TestHandleBillingUnavailableEdgeCases:
    """Edge case tests for HandleBillingUnavailable use case"""

    async def test_zero_amount_billing_failure(
        self,
        mock_retry_job_repository,
        mock_audit_service,
        mock_uow,
    ):
        """Test handling billing failure with zero amount"""
        # Arrange
        use_case = HandleBillingUnavailable(
            retry_job_repository=mock_retry_job_repository,
            audit_service=mock_audit_service,
            uow=mock_uow,
        )

        command = BillingUnavailableCommandDTO(
            step_run_id="step_123",
            tenant_id="tenant_123",
            amount=Decimal("0.00"),
            idempotency_key="key_123",
            retry_attempt=0,
        )

        created_job = RetryJob(
            id="job_001",
            step_run_id="step_123",
            retry_attempt=1,
            scheduled_at=datetime.utcnow() + timedelta(seconds=60),
            status=RetryStatus.pending,
        )
        mock_retry_job_repository.create.return_value = created_job

        # Act
        result = await use_case.execute(command)

        # Assert - should still create retry job (amount validation is billing service concern)
        assert result.is_ok()

    async def test_large_retry_attempt_backoff(
        self,
        mock_retry_job_repository,
        mock_audit_service,
        mock_uow,
    ):
        """Test backoff calculation for high retry attempts (within limit)"""
        # Arrange
        use_case = HandleBillingUnavailable(
            retry_job_repository=mock_retry_job_repository,
            audit_service=mock_audit_service,
            uow=mock_uow,
            max_retries=10,  # Allow more retries for this test
        )

        command = BillingUnavailableCommandDTO(
            step_run_id="step_123",
            tenant_id="tenant_123",
            amount=Decimal("5.00"),
            idempotency_key="key_123",
            retry_attempt=4,  # 5th attempt
        )

        created_job = RetryJob(
            id="job_001",
            step_run_id="step_123",
            retry_attempt=5,
            scheduled_at=datetime.utcnow() + timedelta(seconds=960),
            status=RetryStatus.pending,
        )
        mock_retry_job_repository.create.return_value = created_job

        # Act
        with patch("src.app.use_cases.billing.handle_billing_unavailable.datetime") as mock_dt:
            mock_now = datetime(2024, 1, 1, 12, 0, 0)
            mock_dt.utcnow.return_value = mock_now
            result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        created_retry_job = mock_retry_job_repository.create.call_args[0][0]
        # 60 * 2^4 = 960 seconds = 16 minutes
        expected_scheduled_at = mock_now + timedelta(seconds=960)
        assert created_retry_job.scheduled_at == expected_scheduled_at
