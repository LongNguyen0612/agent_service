"""Billing Use Case DTOs - UC-51

Data Transfer Objects for billing-related use cases.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel


class BillingUnavailableCommandDTO(BaseModel):
    """Command DTO for handling billing service unavailability - UC-51"""

    step_run_id: str
    tenant_id: str
    amount: Decimal
    idempotency_key: str
    retry_attempt: int = 0
    error_message: Optional[str] = None


class BillingUnavailableResponseDTO(BaseModel):
    """Response DTO for billing unavailability handling - UC-51"""

    retry_job_id: str
    scheduled_at: datetime
    message: str
    retry_attempt: int
