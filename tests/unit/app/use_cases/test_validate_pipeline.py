"""Unit Tests for ValidatePipeline Use Case - Story 2.3

Tests validation logic with mocked dependencies.
"""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from src.app.use_cases.validate_pipeline import (
    ValidatePipeline,
    ValidatePipelineCommandDTO,
    ValidationResultDTO,
)
from src.app.services.billing_client import BillingServiceUnavailable, BillingError
from src.app.services.billing_dtos import BalanceResponse
from src.domain.task import Task


@pytest.fixture
def mock_task_repository():
    """Create mock TaskRepository"""
    return MagicMock()


@pytest.fixture
def mock_billing_client():
    """Create mock BillingClient"""
    return MagicMock()


@pytest.fixture
def mock_cost_estimator():
    """Create mock CostEstimator"""
    estimator = MagicMock()
    # Default: estimate 150 credits (as per AC-2.3.4)
    estimator.estimate_pipeline_cost.return_value = Decimal("150.00")
    return estimator


@pytest.fixture
def validate_pipeline(mock_task_repository, mock_billing_client, mock_cost_estimator):
    """Create ValidatePipeline use case with mocked dependencies"""
    return ValidatePipeline(
        task_repository=mock_task_repository,
        billing_client=mock_billing_client,
        cost_estimator=mock_cost_estimator,
    )


@pytest.fixture
def sample_task():
    """Create sample task for testing"""
    return Task(
        id="task_123",
        tenant_id="tenant_abc",
        title="Test Task",
        description="Test description",
        status="pending",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


class TestValidatePipeline:
    """Unit tests for ValidatePipeline use case - AC-2.3.1, AC-2.3.2, AC-2.3.3, AC-2.3.4"""

    @pytest.mark.asyncio
    async def test_validation_success_sufficient_credits(
        self, validate_pipeline, mock_task_repository, mock_billing_client, sample_task
    ):
        """Test AC-2.3.1: Successful validation when tenant has sufficient credits"""
        # Arrange
        mock_task_repository.get_by_id = AsyncMock(return_value=sample_task)
        mock_billing_client.get_balance = AsyncMock(
            return_value=BalanceResponse(
                tenant_id="tenant_abc",
                balance=Decimal("1000.00"),
                last_updated=datetime.utcnow(),
            )
        )

        command = ValidatePipelineCommandDTO(
            task_id="task_123", tenant_id="tenant_abc"
        )

        # Act
        result = await validate_pipeline.execute(command)

        # Assert
        assert result.is_ok()
        dto = result.value
        assert isinstance(dto, ValidationResultDTO)
        assert dto.eligible is True
        assert dto.estimated_cost == Decimal("150.00")
        assert dto.current_balance == Decimal("1000.00")
        assert dto.reason is None

        # Verify task was checked with tenant isolation (AC-2.3.2)
        mock_task_repository.get_by_id.assert_called_once_with(
            task_id="task_123", tenant_id="tenant_abc"
        )

        # Verify balance was retrieved (AC-2.3.3)
        mock_billing_client.get_balance.assert_called_once_with(tenant_id="tenant_abc")

    @pytest.mark.asyncio
    async def test_validation_failure_insufficient_credits(
        self, validate_pipeline, mock_task_repository, mock_billing_client, sample_task
    ):
        """Test AC-2.3.1: Validation fails when tenant has insufficient credits"""
        # Arrange
        mock_task_repository.get_by_id = AsyncMock(return_value=sample_task)
        mock_billing_client.get_balance = AsyncMock(
            return_value=BalanceResponse(
                tenant_id="tenant_abc",
                balance=Decimal("100.00"),  # Less than required 150
                last_updated=datetime.utcnow(),
            )
        )

        command = ValidatePipelineCommandDTO(
            task_id="task_123", tenant_id="tenant_abc"
        )

        # Act
        result = await validate_pipeline.execute(command)

        # Assert
        assert result.is_ok()
        dto = result.value
        assert dto.eligible is False
        assert dto.estimated_cost == Decimal("150.00")
        assert dto.current_balance == Decimal("100.00")
        assert "Insufficient credits" in dto.reason
        assert "Required: 150.00" in dto.reason
        assert "Available: 100.00" in dto.reason

    @pytest.mark.asyncio
    async def test_validation_failure_task_not_found(
        self, validate_pipeline, mock_task_repository, mock_billing_client
    ):
        """Test AC-2.3.2: Validation returns error when task not found or access denied"""
        # Arrange
        mock_task_repository.get_by_id = AsyncMock(return_value=None)

        command = ValidatePipelineCommandDTO(
            task_id="nonexistent_task", tenant_id="tenant_abc"
        )

        # Act
        result = await validate_pipeline.execute(command)

        # Assert - Returns error for 404 handling
        assert result.is_err()
        assert result.error.code == "TASK_NOT_FOUND"
        assert "Task not found or access denied" in result.error.message

        # Verify task lookup was attempted with tenant isolation
        mock_task_repository.get_by_id.assert_called_once_with(
            task_id="nonexistent_task", tenant_id="tenant_abc"
        )

        # Verify billing service was NOT called (short-circuit on task not found)
        mock_billing_client.get_balance.assert_not_called()

    @pytest.mark.asyncio
    async def test_validation_error_billing_service_unavailable(
        self, validate_pipeline, mock_task_repository, mock_billing_client, sample_task
    ):
        """Test AC-2.3.3: Error when billing service is unavailable"""
        # Arrange
        mock_task_repository.get_by_id = AsyncMock(return_value=sample_task)
        mock_billing_client.get_balance = AsyncMock(
            side_effect=BillingServiceUnavailable(
                "Billing service unavailable after 3 attempts"
            )
        )

        command = ValidatePipelineCommandDTO(
            task_id="task_123", tenant_id="tenant_abc"
        )

        # Act
        result = await validate_pipeline.execute(command)

        # Assert
        assert result.is_err()
        assert result.error.code == "BILLING_SERVICE_UNAVAILABLE"
        assert "Billing service is currently unavailable" in result.error.message

    @pytest.mark.asyncio
    async def test_validation_error_balance_check_failed(
        self, validate_pipeline, mock_task_repository, mock_billing_client, sample_task
    ):
        """Test AC-2.3.3: Error when balance check fails"""
        # Arrange
        mock_task_repository.get_by_id = AsyncMock(return_value=sample_task)
        mock_billing_client.get_balance = AsyncMock(
            side_effect=BillingError("Invalid tenant ID", status_code=400)
        )

        command = ValidatePipelineCommandDTO(
            task_id="task_123", tenant_id="tenant_abc"
        )

        # Act
        result = await validate_pipeline.execute(command)

        # Assert
        assert result.is_err()
        assert result.error.code == "BALANCE_CHECK_FAILED"
        assert "Failed to check credit balance" in result.error.message

    @pytest.mark.asyncio
    async def test_validation_uses_hardcoded_cost_estimate(
        self, validate_pipeline, mock_task_repository, mock_billing_client, mock_cost_estimator, sample_task
    ):
        """Test AC-2.3.4: Validation uses hardcoded cost estimate (150 credits)"""
        # Arrange
        mock_task_repository.get_by_id = AsyncMock(return_value=sample_task)
        mock_billing_client.get_balance = AsyncMock(
            return_value=BalanceResponse(
                tenant_id="tenant_abc",
                balance=Decimal("200.00"),
                last_updated=datetime.utcnow(),
            )
        )

        command = ValidatePipelineCommandDTO(
            task_id="task_123", tenant_id="tenant_abc"
        )

        # Act
        result = await validate_pipeline.execute(command)

        # Assert
        assert result.is_ok()
        dto = result.value
        assert dto.estimated_cost == Decimal("150.00")

        # Verify cost estimator was called
        mock_cost_estimator.estimate_pipeline_cost.assert_called_once()

    @pytest.mark.asyncio
    async def test_validation_exact_balance_match(
        self, validate_pipeline, mock_task_repository, mock_billing_client, sample_task
    ):
        """Test edge case: validation succeeds when balance exactly matches cost"""
        # Arrange
        mock_task_repository.get_by_id = AsyncMock(return_value=sample_task)
        mock_billing_client.get_balance = AsyncMock(
            return_value=BalanceResponse(
                tenant_id="tenant_abc",
                balance=Decimal("150.00"),  # Exactly matches required cost
                last_updated=datetime.utcnow(),
            )
        )

        command = ValidatePipelineCommandDTO(
            task_id="task_123", tenant_id="tenant_abc"
        )

        # Act
        result = await validate_pipeline.execute(command)

        # Assert
        assert result.is_ok()
        dto = result.value
        assert dto.eligible is True  # Should be eligible (balance >= cost)
        assert dto.estimated_cost == Decimal("150.00")
        assert dto.current_balance == Decimal("150.00")
        assert dto.reason is None
