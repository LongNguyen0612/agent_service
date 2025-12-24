"""Billing Client Interface - Story 2.2

Abstract interface for billing service integration with custom exceptions.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from decimal import Decimal
from .billing_dtos import CreditTransactionResponse, BalanceResponse


# Custom Exceptions - AC-2.2.3


class BillingError(Exception):
    """Base exception for all billing-related errors"""
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class InsufficientCreditsError(BillingError):
    """Raised when tenant has insufficient credits (402 Payment Required)"""
    def __init__(self, message: str):
        super().__init__(message, status_code=402)


class BillingServiceUnavailable(BillingError):
    """Raised when billing service is unavailable (5xx errors or timeout)"""
    def __init__(self, message: str = "Billing service is currently unavailable"):
        super().__init__(message, status_code=503)


# Billing Client Interface - AC-2.2.1, AC-2.2.2, AC-2.2.3


class BillingClient(ABC):
    """
    Abstract interface for billing service integration.

    Defines methods for consuming credits, refunding credits, and checking balances
    during pipeline execution.
    """

    @abstractmethod
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
        Consume credits from tenant balance.

        Args:
            tenant_id: Tenant identifier
            amount: Credit amount to consume
            idempotency_key: Unique key for idempotent operations
            reference_type: Optional type of reference (e.g., 'pipeline_run')
            reference_id: Optional ID of referenced entity
            metadata: Optional metadata for audit trail

        Returns:
            CreditTransactionResponse with transaction details

        Raises:
            InsufficientCreditsError: When tenant has insufficient credits (402)
            BillingError: On client errors (4xx)
            BillingServiceUnavailable: On server errors (5xx) or timeout
        """
        pass

    @abstractmethod
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
        Refund credits back to tenant balance.

        Args:
            tenant_id: Tenant identifier
            amount: Credit amount to refund
            idempotency_key: Unique key for idempotent operations
            reference_type: Optional type of reference
            reference_id: Optional ID of referenced entity
            metadata: Optional metadata (should include original_transaction_id)

        Returns:
            CreditTransactionResponse with transaction details

        Raises:
            BillingError: On client errors (4xx)
            BillingServiceUnavailable: On server errors (5xx) or timeout
        """
        pass

    @abstractmethod
    async def get_balance(self, tenant_id: str) -> BalanceResponse:
        """
        Get current credit balance for tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            BalanceResponse with current balance

        Raises:
            BillingError: On not found (404) or other client errors
            BillingServiceUnavailable: On server errors (5xx) or timeout
        """
        pass
