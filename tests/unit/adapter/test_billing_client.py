"""Unit Tests for HTTP Billing Client - Story 2.2

Tests billing client with mocked HTTP responses.
"""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from src.adapter.services.http_billing_client import HttpBillingClient
from src.app.services.billing_client import (
    InsufficientCreditsError,
    BillingError,
    BillingServiceUnavailable,
)


@pytest.fixture
def billing_client():
    """Create billing client for testing"""
    return HttpBillingClient(base_url="http://billing-test:8000")


@pytest.fixture
def mock_response():
    """Create mock HTTP response"""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    return response


class TestHttpBillingClient:
    """Unit tests for HttpBillingClient - AC-2.2.1, AC-2.2.2, AC-2.2.3"""

    @pytest.mark.asyncio
    async def test_consume_credits_success(self, billing_client, mock_response):
        """Test AC-2.2.1: consume_credits returns CreditTransactionResponse on 200"""
        # Arrange
        mock_response.json.return_value = {
            "transaction_id": "txn_123",
            "tenant_id": "tenant_abc",
            "transaction_type": "consume",
            "amount": "50.00",
            "balance_before": "1000.00",
            "balance_after": "950.00",
            "idempotency_key": "test_key",
            "created_at": "2024-01-01T00:00:00Z"
        }

        with patch.object(billing_client, '_retry_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            # Act
            result = await billing_client.consume_credits(
                tenant_id="tenant_abc",
                amount=Decimal("50.00"),
                idempotency_key="test_key"
            )

            # Assert
            assert result.transaction_id == "txn_123"
            assert result.tenant_id == "tenant_abc"
            assert result.amount == Decimal("50.00")
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_consume_credits_insufficient(self, billing_client, mock_response):
        """Test AC-2.2.1: consume_credits raises InsufficientCreditsError on 402"""
        # Arrange
        mock_response.status_code = 402
        mock_response.json.return_value = {
            "error": {
                "code": "INSUFFICIENT_CREDIT",
                "message": "Insufficient credits. Required: 100, Available: 50"
            }
        }

        with patch.object(billing_client, '_retry_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            # Act & Assert
            with pytest.raises(InsufficientCreditsError) as exc_info:
                await billing_client.consume_credits(
                    tenant_id="tenant_abc",
                    amount=Decimal("100.00"),
                    idempotency_key="test_key"
                )

            assert "Insufficient credits" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_consume_credits_timeout(self, billing_client):
        """Test AC-2.2.5: consume_credits raises BillingServiceUnavailable on timeout"""
        # Arrange
        with patch.object(billing_client, '_retry_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = BillingServiceUnavailable("Billing service unavailable after 3 attempts")

            # Act & Assert
            with pytest.raises(BillingServiceUnavailable):
                await billing_client.consume_credits(
                    tenant_id="tenant_abc",
                    amount=Decimal("50.00"),
                    idempotency_key="test_key"
                )

    @pytest.mark.asyncio
    async def test_consume_credits_server_error(self, billing_client, mock_response):
        """Test AC-2.2.1: consume_credits raises BillingServiceUnavailable on 5xx"""
        # Arrange
        mock_response.status_code = 503
        mock_response.json.return_value = {"error": {"message": "Service unavailable"}}

        with patch.object(billing_client, '_retry_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            # Act & Assert
            with pytest.raises(BillingServiceUnavailable):
                await billing_client.consume_credits(
                    tenant_id="tenant_abc",
                    amount=Decimal("50.00"),
                    idempotency_key="test_key"
                )

    @pytest.mark.asyncio
    async def test_refund_credits_success(self, billing_client, mock_response):
        """Test AC-2.2.2: refund_credits returns CreditTransactionResponse on 200"""
        # Arrange
        mock_response.json.return_value = {
            "transaction_id": "txn_456",
            "tenant_id": "tenant_abc",
            "transaction_type": "refund",
            "amount": "30.00",
            "balance_before": "950.00",
            "balance_after": "980.00",
            "idempotency_key": "refund_key",
            "created_at": "2024-01-01T00:00:00Z"
        }

        with patch.object(billing_client, '_retry_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            # Act
            result = await billing_client.refund_credits(
                tenant_id="tenant_abc",
                amount=Decimal("30.00"),
                idempotency_key="refund_key",
                metadata={"original_transaction_id": "txn_123", "reason": "test refund"}
            )

            # Assert
            assert result.transaction_id == "txn_456"
            assert result.transaction_type == "refund"
            assert result.amount == Decimal("30.00")

    @pytest.mark.asyncio
    async def test_get_balance_success(self, billing_client, mock_response):
        """Test AC-2.2.3: get_balance returns BalanceResponse on 200"""
        # Arrange
        mock_response.json.return_value = {
            "tenant_id": "tenant_abc",
            "balance": "1000.50",
            "last_updated": "2024-01-01T00:00:00Z"
        }

        with patch.object(billing_client, '_retry_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            # Act
            result = await billing_client.get_balance(tenant_id="tenant_abc")

            # Assert
            assert result.tenant_id == "tenant_abc"
            assert result.balance == Decimal("1000.50")
            mock_request.assert_called_once_with(
                "GET",
                "http://billing-test:8000/billing/credits/balance/tenant_abc"
            )

    @pytest.mark.asyncio
    async def test_get_balance_not_found(self, billing_client, mock_response):
        """Test AC-2.2.3: get_balance raises BillingError on 404"""
        # Arrange
        mock_response.status_code = 404
        mock_response.json.return_value = {
            "error": {
                "code": "LEDGER_NOT_FOUND",
                "message": "No credit ledger found for tenant tenant_abc"
            }
        }

        with patch.object(billing_client, '_retry_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            # Act & Assert
            with pytest.raises(BillingError) as exc_info:
                await billing_client.get_balance(tenant_id="tenant_abc")

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_retry_with_exponential_backoff(self, billing_client):
        """Test AC-2.2.5: _retry_request retries with exponential backoff (1s, 2s, 4s)"""
        # Arrange
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        billing_client.client = mock_client

        # Simulate: 1st attempt fails, 2nd attempt fails, 3rd attempt succeeds
        success_response = MagicMock(spec=httpx.Response)
        success_response.status_code = 200

        mock_client.request.side_effect = [
            httpx.TimeoutException("Timeout 1"),
            httpx.TimeoutException("Timeout 2"),
            success_response
        ]

        # Act
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            result = await billing_client._retry_request("GET", "http://test/api")

            # Assert
            assert mock_client.request.call_count == 3
            assert mock_sleep.call_count == 2  # Slept twice: after 1st and 2nd attempts
            # Check exponential backoff delays: 1s, 2s
            assert mock_sleep.call_args_list[0][0][0] == 1
            assert mock_sleep.call_args_list[1][0][0] == 2
            assert result == success_response
