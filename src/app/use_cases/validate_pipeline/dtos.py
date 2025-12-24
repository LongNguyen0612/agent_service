"""DTOs for Validate Pipeline Use Case - Story 2.3

Defines command and response DTOs for pipeline validation.
"""
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel


class ValidatePipelineCommandDTO(BaseModel):
    """Command DTO for ValidatePipeline use case - AC-2.3.1

    Attributes:
        task_id: ID of the task to validate
        tenant_id: ID of the tenant requesting validation
    """
    task_id: str
    tenant_id: str


class ValidationResultDTO(BaseModel):
    """Response DTO for ValidatePipeline use case - AC-2.3.1

    Attributes:
        eligible: True if pipeline can proceed, False otherwise
        estimated_cost: Estimated cost in credits for full pipeline (4 steps)
        current_balance: Current credit balance for the tenant
        reason: Optional reason why pipeline cannot proceed (if eligible=False)

    Examples:
        Success case (eligible):
        {
            "eligible": true,
            "estimated_cost": "150.00",
            "current_balance": "1000.00",
            "reason": null
        }

        Failure case (insufficient credits):
        {
            "eligible": false,
            "estimated_cost": "150.00",
            "current_balance": "100.00",
            "reason": "Insufficient credits. Required: 150, Available: 100"
        }

        Failure case (task not found):
        {
            "eligible": false,
            "estimated_cost": "0.00",
            "current_balance": "1000.00",
            "reason": "Task not found or access denied"
        }
    """
    eligible: bool
    estimated_cost: Decimal
    current_balance: Decimal
    reason: Optional[str] = None
