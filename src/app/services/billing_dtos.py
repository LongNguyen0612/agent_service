"""Billing Service DTOs - Story 2.2

Response models for billing service integration.
"""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class CreditTransactionResponse(BaseModel):
    """
    Response DTO for credit consume/refund operations.
    Maps to billing_service response format.
    """
    transaction_id: str
    tenant_id: str
    transaction_type: str  # "consume" or "refund"
    amount: Decimal
    balance_before: Decimal
    balance_after: Decimal
    idempotency_key: str
    created_at: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "transaction_id": "txn_abc123",
                "tenant_id": "tenant_xyz",
                "transaction_type": "consume",
                "amount": "50.00",
                "balance_before": "1000.00",
                "balance_after": "950.00",
                "idempotency_key": "pipeline_run_123:step_1",
                "created_at": "2024-01-01T00:00:00Z"
            }
        }


class BalanceResponse(BaseModel):
    """
    Response DTO for balance query operations.
    Maps to billing_service balance response.
    """
    tenant_id: str
    balance: Decimal
    last_updated: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "tenant_xyz",
                "balance": "969.50",
                "last_updated": "2024-01-01T00:00:00Z"
            }
        }
