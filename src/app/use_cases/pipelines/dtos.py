from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class PipelineStepDTO(BaseModel):
    """Response DTO for a single pipeline step"""

    id: str
    step_number: int
    step_name: str
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    output: Optional[Dict[str, Any]]
    error_message: Optional[str]


class PipelineTimelineResponseDTO(BaseModel):
    """Response DTO for pipeline timeline"""

    id: str  # Changed from pipeline_run_id to match frontend expectations
    task_id: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]
    steps: List[PipelineStepDTO]
