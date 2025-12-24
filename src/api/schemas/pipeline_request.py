"""Request schemas for Pipeline API - Story 2.7"""
from typing import Optional
from pydantic import BaseModel, Field


class CancelPipelineRequest(BaseModel):
    """Request body for cancelling a pipeline - AC-2.7.4"""
    reason: Optional[str] = Field(None, description="Optional reason for cancellation")


class ResumePipelineRequest(BaseModel):
    """Request body for resuming a paused pipeline - AC-2.7.5"""
    # No body params needed - pipeline_run_id from path
    pass
