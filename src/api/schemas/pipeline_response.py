"""Response schemas for Pipeline API - Story 2.7"""
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class ArtifactSummary(BaseModel):
    """Summary of an artifact in pipeline status - AC-2.7.3"""
    id: str
    artifact_type: str
    status: str
    created_at: datetime


class StepSummary(BaseModel):
    """Summary of a step in pipeline status - AC-2.7.3"""
    id: str
    step_number: int
    step_type: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int
    artifact: Optional[ArtifactSummary] = None


class PipelineStatusResponse(BaseModel):
    """Full pipeline state response - AC-2.7.3

    Example:
        {
            "pipeline_run_id": "pipeline_abc123",
            "task_id": "task_xyz",
            "status": "running",
            "current_step": 2,
            "pause_reasons": [],
            "total_credits_consumed": 150,
            "steps": [...],
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:05:00Z"
        }
    """
    pipeline_run_id: str
    task_id: str
    tenant_id: str
    status: str
    current_step: int
    pause_reasons: List[str] = Field(default_factory=list)
    total_credits_consumed: Decimal
    steps: List[StepSummary] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    paused_at: Optional[datetime] = None
    pause_expires_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class PipelineListItem(BaseModel):
    """Pipeline summary for list endpoint - AC-2.7.6"""
    pipeline_run_id: str
    task_id: str
    status: str
    current_step: int
    created_at: datetime
    updated_at: datetime


class PipelineListResponse(BaseModel):
    """Paginated list of pipelines - AC-2.7.6

    Example:
        {
            "items": [...],
            "total": 100,
            "limit": 20,
            "offset": 0
        }
    """
    items: List[PipelineListItem]
    total: int
    limit: int
    offset: int


class AgentRunDetails(BaseModel):
    """Agent run details for step details - AC-2.7.7"""
    id: str
    agent_type: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_credits: int
    actual_cost_credits: int
    started_at: datetime
    completed_at: datetime


class StepDetailsResponse(BaseModel):
    """Detailed step information - AC-2.7.7

    Example:
        {
            "step_id": "step_123",
            "pipeline_run_id": "pipeline_abc",
            "step_number": 1,
            "step_type": "ANALYSIS",
            "status": "completed",
            "retry_count": 0,
            "max_retries": 3,
            "started_at": "...",
            "completed_at": "...",
            "agent_run": {...},
            "artifact": {...}
        }
    """
    step_id: str
    pipeline_run_id: str
    step_number: int
    step_type: str
    status: str
    retry_count: int
    max_retries: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    input_snapshot: Optional[dict] = None
    agent_run: Optional[AgentRunDetails] = None
    artifact: Optional[ArtifactSummary] = None


class ValidationResponse(BaseModel):
    """Response for pipeline validation - AC-2.7.1

    Example (eligible):
        {
            "eligible": true,
            "estimated_cost": 500,
            "current_balance": 1000,
            "reason": null
        }

    Example (not eligible):
        {
            "eligible": false,
            "estimated_cost": 500,
            "current_balance": 200,
            "reason": "INSUFFICIENT_CREDITS"
        }
    """
    eligible: bool
    estimated_cost: Decimal
    current_balance: Decimal
    reason: Optional[str] = None


class RunPipelineResponse(BaseModel):
    """Response for run pipeline endpoint - AC-2.7.2

    Example:
        {
            "pipeline_run_id": "pipeline_abc123",
            "status": "running",
            "current_step": 1,
            "message": "Pipeline started successfully"
        }
    """
    pipeline_run_id: str
    status: str
    current_step: int
    message: str = "Pipeline started successfully"


class CancelPipelineResponse(BaseModel):
    """Response for cancel pipeline endpoint - AC-2.7.4"""
    pipeline_run_id: str
    previous_status: str
    new_status: str
    steps_completed: int
    steps_cancelled: int
    message: str


class ResumePipelineResponse(BaseModel):
    """Response for resume pipeline endpoint - AC-2.7.5"""
    pipeline_run_id: str
    status: str
    current_step: int
    message: str
