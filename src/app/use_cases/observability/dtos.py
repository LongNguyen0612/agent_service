"""
DTOs for Observability Use Cases (UC-61)

Data Transfer Objects for viewing AI cost breakdowns per task.
"""

from decimal import Decimal
from typing import List

from pydantic import BaseModel


class TaskCostBreakdownDTO(BaseModel):
    """DTO for individual step/agent cost breakdown"""

    step: str
    agent: str
    cost: Decimal


class ViewTaskCostResponseDTO(BaseModel):
    """Response DTO for viewing task cost (UC-61)"""

    task_id: str
    total_cost: Decimal
    breakdown: List[TaskCostBreakdownDTO]
