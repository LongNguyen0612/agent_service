"""DTOs for Pipeline Use Cases - Stories 2.4, 2.6

Defines command and response DTOs for pipeline execution.
"""
from typing import Optional
from pydantic import BaseModel


class RunPipelineCommandDTO(BaseModel):
    """
    Command DTO for RunPipelineStep use case - AC-2.4.1, Task 2.4.4

    Attributes:
        task_id: ID of the task to execute
        tenant_id: ID of the tenant requesting execution
    """
    task_id: str
    tenant_id: str


class PipelineStepResultDTO(BaseModel):
    """
    Response DTO for RunPipelineStep use case - AC-2.4.5, Task 2.4.4

    Attributes:
        pipeline_run_id: ID of the pipeline run
        step_number: Current step number (1-4)
        step_type: Type of step (ANALYSIS, USER_STORIES, CODE_SKELETON, TEST_CASES)
        status: Status of the step (running, completed, failed, etc.)
        artifact_id: ID of the created artifact (if step completed successfully)

    Examples:
        Success case (step completed):
        {
            "pipeline_run_id": "pipeline_abc123",
            "step_number": 1,
            "step_type": "ANALYSIS",
            "status": "completed",
            "artifact_id": "artifact_xyz789"
        }

        Running case (step in progress):
        {
            "pipeline_run_id": "pipeline_abc123",
            "step_number": 2,
            "step_type": "USER_STORIES",
            "status": "running",
            "artifact_id": null
        }
    """
    pipeline_run_id: str
    step_number: int
    step_type: str
    status: str
    artifact_id: Optional[str] = None


class CancelPipelineCommandDTO(BaseModel):
    """
    Command DTO for CancelPipeline use case - AC-2.6.1, Story 2.6

    Attributes:
        pipeline_run_id: ID of the pipeline run to cancel
        tenant_id: ID of the tenant (for authorization)
        user_id: ID of the user requesting cancellation (for audit)
        reason: Optional reason for cancellation
    """
    pipeline_run_id: str
    tenant_id: str
    user_id: str
    reason: Optional[str] = None


class CancellationResultDTO(BaseModel):
    """
    Response DTO for CancelPipeline use case - AC-2.6.1, Story 2.6

    Attributes:
        pipeline_run_id: ID of the cancelled pipeline run
        previous_status: Status before cancellation
        new_status: Status after cancellation (should be 'cancelled')
        steps_completed: Number of steps that were completed
        steps_cancelled: Number of steps that were cancelled or not started
        message: Human-readable cancellation message

    Example:
        {
            "pipeline_run_id": "pipeline_abc123",
            "previous_status": "running",
            "new_status": "cancelled",
            "steps_completed": 2,
            "steps_cancelled": 2,
            "message": "Pipeline cancelled successfully. 2 completed steps preserved."
        }
    """
    pipeline_run_id: str
    previous_status: str
    new_status: str
    steps_completed: int
    steps_cancelled: int
    message: str


class ReplayPipelineCommandDTO(BaseModel):
    """
    Command DTO for ReplayPipeline use case (UC-25)

    Attributes:
        pipeline_run_id: ID of the pipeline run to replay
        tenant_id: ID of the tenant (for authorization)
        from_step_id: Optional step ID to replay from (replays entire pipeline if None)
        preserve_approved_artifacts: Whether to preserve approved artifacts from previous run
    """
    pipeline_run_id: str
    tenant_id: str
    from_step_id: Optional[str] = None
    preserve_approved_artifacts: bool = True


class ReplayPipelineResponseDTO(BaseModel):
    """
    Response DTO for ReplayPipeline use case (UC-25)

    Attributes:
        new_pipeline_run_id: ID of the newly created pipeline run
        status: Status of the new pipeline run
        started_from_step: Name of the step the replay started from

    Example:
        {
            "new_pipeline_run_id": "new_run_uuid",
            "status": "running",
            "started_from_step": "ANALYSIS"
        }
    """
    new_pipeline_run_id: str
    status: str
    started_from_step: str
