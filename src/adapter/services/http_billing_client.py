"""HTTP Billing Client Implementation - Story 2.2

Concrete implementation of BillingClient using httpx with timeout and retry logic.
"""
import logging
import httpx
from typing import Optional, Dict, Any
from decimal import Decimal
from src.app.services.billing_client import (
    BillingClient,
    BillingError,
    InsufficientCreditsError,
    BillingServiceUnavailable,
)
from src.app.services.billing_dtos import CreditTransactionResponse, BalanceResponse

logger = logging.getLogger(__name__)


class HttpBillingClient(BillingClient):
    """
    HTTP implementation of BillingClient using httpx.

    Features:
    - 5 second timeout per request (AC-2.2.5)
    - Exponential backoff retry: 1s, 2s, 4s (AC-2.2.5)
    - Proper error mapping to custom exceptions (AC-2.2.1, AC-2.2.2, AC-2.2.3)
    """

    def __init__(self, base_url: str, timeout: float = 5.0, max_retries: int = 3):
        """
        Initialize HTTP billing client.

        Args:
            base_url: Base URL of billing service (e.g., "http://billing_api:8000")
            timeout: Request timeout in seconds (default: 5.0)
            max_retries: Maximum retry attempts (default: 3)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.client = httpx.AsyncClient(timeout=timeout)

    async def _retry_request(self, method: str, url: str, **kwargs):
        """
        Execute HTTP request with exponential backoff retry.

        Retry delays: 1s, 2s, 4s for up to 3 attempts (AC-2.2.5)
        """
        import asyncio

        last_exception = None
        for attempt in range(self.max_retries):
            try:
                response = await self.client.request(method, url, **kwargs)
                return response
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    delay = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(
                        f"Billing request failed (attempt {attempt + 1}/{self.max_retries}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Billing request failed after {self.max_retries} attempts: {e}"
                    )

        # All retries exhausted
        raise BillingServiceUnavailable(
            f"Billing service unavailable after {self.max_retries} attempts"
        )

    async def consume_credits(
        self,
        tenant_id: str,
        amount: Decimal,
        idempotency_key: str,
        reference_type: Optional[str] = None,
        reference_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> CreditTransactionResponse:
        """
        Consume credits from tenant balance via HTTP POST.

        Implements AC-2.2.1:
        - POST to /billing/credits/consume
        - Maps 402 → InsufficientCreditsError
        - Maps 5xx/timeout → BillingServiceUnavailable
        """
        url = f"{self.base_url}/billing/credits/consume"
        payload = {
            "tenant_id": tenant_id,
            "amount": str(amount),  # Serialize Decimal as string
            "idempotency_key": idempotency_key,
        }
        if reference_type:
            payload["reference_type"] = reference_type
        if reference_id:
            payload["reference_id"] = reference_id
        if metadata:
            payload["metadata"] = metadata

        try:
            response = await self._retry_request("POST", url, json=payload)

            # Handle 402 Payment Required
            if response.status_code == 402:
                error_data = response.json()
                error_message = error_data.get("error", {}).get(
                    "message", "Insufficient credits"
                )
                logger.warning(f"Insufficient credits for tenant {tenant_id}: {error_message}")
                raise InsufficientCreditsError(error_message)

            # Handle 5xx Server Errors
            if response.status_code >= 500:
                logger.error(f"Billing service error (5xx): {response.status_code}")
                raise BillingServiceUnavailable(
                    f"Billing service returned {response.status_code}"
                )

            # Handle other 4xx Client Errors
            if 400 <= response.status_code < 500:
                error_data = response.json()
                error_message = error_data.get("error", {}).get("message", "Client error")
                logger.error(f"Billing client error: {error_message}")
                raise BillingError(error_message, status_code=response.status_code)

            # Success (200)
            response.raise_for_status()
            return CreditTransactionResponse(**response.json())

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error consuming credits: {e}")
            raise BillingError(f"HTTP error: {e}", status_code=e.response.status_code)

    async def refund_credits(
        self,
        tenant_id: str,
        amount: Decimal,
        idempotency_key: str,
        reference_type: Optional[str] = None,
        reference_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> CreditTransactionResponse:
        """
        Refund credits back to tenant balance via HTTP POST.

        Implements AC-2.2.2:
        - POST to /billing/credits/refund
        - Maps errors appropriately
        """
        url = f"{self.base_url}/billing/credits/refund"
        payload = {
            "tenant_id": tenant_id,
            "amount": str(amount),  # Serialize Decimal as string
            "idempotency_key": idempotency_key,
        }
        if reference_type:
            payload["reference_type"] = reference_type
        if reference_id:
            payload["reference_id"] = reference_id
        if metadata:
            payload["metadata"] = metadata

        try:
            response = await self._retry_request("POST", url, json=payload)

            # Handle 5xx Server Errors
            if response.status_code >= 500:
                logger.error(f"Billing service error (5xx): {response.status_code}")
                raise BillingServiceUnavailable(
                    f"Billing service returned {response.status_code}"
                )

            # Handle 4xx Client Errors
            if 400 <= response.status_code < 500:
                error_data = response.json()
                error_message = error_data.get("error", {}).get("message", "Client error")
                logger.error(f"Billing client error: {error_message}")
                raise BillingError(error_message, status_code=response.status_code)

            # Success (200)
            response.raise_for_status()
            return CreditTransactionResponse(**response.json())

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error refunding credits: {e}")
            raise BillingError(f"HTTP error: {e}", status_code=e.response.status_code)

    async def get_balance(self, tenant_id: str) -> BalanceResponse:
        """
        Get current credit balance for tenant via HTTP GET.

        Implements AC-2.2.3:
        - GET to /billing/credits/balance/{tenant_id}
        - Maps 404 → BillingError
        - Maps errors appropriately
        """
        url = f"{self.base_url}/billing/credits/balance/{tenant_id}"

        try:
            response = await self._retry_request("GET", url)

            # Handle 404 Not Found
            if response.status_code == 404:
                error_data = response.json()
                error_message = error_data.get("error", {}).get("message", "Ledger not found")
                logger.warning(f"Ledger not found for tenant {tenant_id}")
                raise BillingError(error_message, status_code=404)

            # Handle 5xx Server Errors
            if response.status_code >= 500:
                logger.error(f"Billing service error (5xx): {response.status_code}")
                raise BillingServiceUnavailable(
                    f"Billing service returned {response.status_code}"
                )

            # Handle other 4xx Client Errors
            if 400 <= response.status_code < 500:
                error_data = response.json()
                error_message = error_data.get("error", {}).get("message", "Client error")
                logger.error(f"Billing client error: {error_message}")
                raise BillingError(error_message, status_code=response.status_code)

            # Success (200)
            response.raise_for_status()
            return BalanceResponse(**response.json())

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting balance: {e}")
            raise BillingError(f"HTTP error: {e}", status_code=e.response.status_code)

    async def close(self):
        """Close the HTTP client connection"""
        await self.client.aclose()
