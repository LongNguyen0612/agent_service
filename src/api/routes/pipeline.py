"""Pipeline API Routes - Story 2.7

Provides HTTP endpoints for pipeline operations including:
- Validation, execution, status, cancellation, resumption
- Listing and detailed step information
"""
from typing import Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, status, HTTPException
from src.api.error import ClientError, ServerError
from src.api.schemas.pipeline_request import CancelPipelineRequest, ResumePipelineRequest
from src.api.schemas.pipeline_response import (
    ValidationResponse,
    RunPipelineResponse,
    PipelineStatusResponse,
    CancelPipelineResponse,
    ResumePipelineResponse,
    PipelineListResponse,
    PipelineListItem,
    StepDetailsResponse,
    StepSummary,
    ArtifactSummary,
    AgentRunDetails,
)
from src.app.repositories.task_repository import TaskRepository
from src.app.repositories.pipeline_run_repository import IPipelineRunRepository
from src.app.repositories.pipeline_step_repository import IPipelineStepRunRepository
from src.app.repositories.agent_run_repository import IAgentRunRepository
from src.app.repositories.artifact_repository import IArtifactRepository
from src.app.use_cases.validate_pipeline import ValidatePipeline, ValidatePipelineCommandDTO
from src.app.use_cases.pipeline.run_pipeline_step import RunPipelineStep
from src.app.use_cases.pipeline.cancel_pipeline import CancelPipeline
from src.app.use_cases.pipeline.dtos import (
    RunPipelineCommandDTO,
    CancelPipelineCommandDTO,
)
from src.depends import get_current_user, get_session, get_billing_client
from src.app.services.billing_client import BillingClient
from src.adapter.services.http_billing_client import HttpBillingClient
from src.app.services.cost_estimator import CostEstimator
from src.adapter.repositories.task_repository import SqlAlchemyTaskRepository
from src.adapter.repositories.pipeline_run_repository import PipelineRunRepository
from src.adapter.repositories.pipeline_step_repository import PipelineStepRunRepository
from src.adapter.repositories.agent_run_repository import AgentRunRepository
from src.adapter.repositories.artifact_repository import ArtifactRepository
from src.domain.enums import PipelineStatus
from sqlmodel.ext.asyncio.session import AsyncSession
from libs.result import Error
from config import ApplicationConfig
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


# AC-2.7.1: Validate Pipeline Endpoint
@router.post(
    "/tasks/{task_id}/validate",
    response_model=ValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate pipeline eligibility",
    description="Check if a task is eligible for pipeline execution based on credits and other constraints"
)
async def validate_pipeline(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    billing_client: BillingClient = Depends(get_billing_client),
):
    """
    Validate if pipeline can be executed for a task.

    Returns:
        - 200: ValidationResponse with eligibility status
        - 404: Task not found
    """
    tenant_id = current_user["tenant_id"]

    # Initialize repositories and services
    task_repo = SqlAlchemyTaskRepository(session)
    cost_estimator = CostEstimator()

    # Execute use case
    use_case = ValidatePipeline(
        task_repository=task_repo,
        billing_client=billing_client,
        cost_estimator=cost_estimator,
    )

    result = await use_case.execute(
        ValidatePipelineCommandDTO(task_id=task_id, tenant_id=tenant_id)
    )

    if result.is_err():
        if result.error.code == "TASK_NOT_FOUND":
            raise HTTPException(status_code=404, detail=result.error.message)
        raise ClientError(result.error)

    dto = result.value
    return ValidationResponse(
        eligible=dto.eligible,
        estimated_cost=dto.estimated_cost,
        current_balance=dto.current_balance,
        reason=dto.reason,
    )


# AC-2.7.2: Run Pipeline Endpoint
@router.post(
    "/tasks/{task_id}/run",
    response_model=RunPipelineResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start pipeline execution",
    description="Initiate asynchronous pipeline execution for a task (validates first, then starts)"
)
async def run_pipeline(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    billing_client: BillingClient = Depends(get_billing_client),
):
    """
    Start pipeline execution (async operation).

    Flow:
        1. Validate pipeline eligibility
        2. If eligible, start execution
        3. Return 202 Accepted with pipeline_run_id

    Returns:
        - 202: RunPipelineResponse with pipeline details
        - 400: Validation failed (insufficient credits, etc.)
        - 404: Task not found
    """
    tenant_id = current_user["tenant_id"]

    # Initialize repositories
    task_repo = SqlAlchemyTaskRepository(session)
    pipeline_run_repo = PipelineRunRepository(session)
    step_run_repo = PipelineStepRunRepository(session)
    agent_run_repo = AgentRunRepository(session)
    artifact_repo = ArtifactRepository(session)
    cost_estimator = CostEstimator()

    # Step 1: Validate first
    validate_use_case = ValidatePipeline(
        task_repository=task_repo,
        billing_client=billing_client,
        cost_estimator=cost_estimator,
    )

    validation = await validate_use_case.execute(
        ValidatePipelineCommandDTO(task_id=task_id, tenant_id=tenant_id)
    )

    if validation.is_err():
        if validation.error.code == "TASK_NOT_FOUND":
            raise HTTPException(status_code=404, detail=validation.error.message)
        raise ClientError(validation.error)

    if not validation.value.eligible:
        raise ClientError(
            Error(
                code=validation.value.reason or "NOT_ELIGIBLE",
                message="Pipeline cannot start: " + (validation.value.reason or "Unknown reason"),
            )
        )

    # Step 2: Start execution (note: actual agent execution would be async)
    # For MVP, this is synchronous but returns immediately
    # TODO: In production, move to background task/queue

    logger.info(f"Starting pipeline for task {task_id}")

    return RunPipelineResponse(
        pipeline_run_id="pipeline_" + task_id,  # Placeholder
        status="running",
        current_step=1,
        message="Pipeline execution initiated",
    )


# AC-2.7.6: List Tenant Pipelines Endpoint (MUST be before /{pipeline_run_id} to avoid route conflict)
@router.get(
    "/pipelines",
    response_model=PipelineListResponse,
    status_code=status.HTTP_200_OK,
    summary="List pipelines",
    description="Get paginated list of pipelines for current tenant with optional status filter"
)
async def list_pipelines(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by pipeline status"),
    limit: int = Query(20, ge=1, le=100, description="Number of items per page"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    List pipelines for tenant with pagination.

    Query Parameters:
        - status: Filter by status (running, paused, completed, cancelled)
        - limit: Items per page (1-100, default 20)
        - offset: Items to skip (default 0)

    Returns:
        - 200: PipelineListResponse with paginated items
    """
    from sqlmodel import select, func

    tenant_id = current_user["tenant_id"]

    # Build query
    from src.domain.pipeline_run import PipelineRun
    query = select(PipelineRun).where(PipelineRun.tenant_id == tenant_id)

    # Apply status filter if provided
    if status_filter:
        try:
            status_enum = PipelineStatus(status_filter)
            query = query.where(PipelineRun.status == status_enum)
        except ValueError:
            raise ClientError(
                Error(code="INVALID_STATUS", message=f"Invalid status filter: {status_filter}")
            )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar()

    # Get paginated results
    query = query.order_by(PipelineRun.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    pipelines = list(result.scalars().all())

    # Map to response
    items = [
        PipelineListItem(
            pipeline_run_id=p.id,
            task_id=p.task_id,
            status=p.status.value,
            current_step=p.current_step,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in pipelines
    ]

    return PipelineListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


# AC-2.7.3: Get Pipeline Status Endpoint
@router.get(
    "/{pipeline_run_id}",
    response_model=PipelineStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get pipeline status",
    description="Retrieve full state of a pipeline run including steps, artifacts, and credits consumed"
)
async def get_pipeline_status(
    pipeline_run_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Get full pipeline state.

    Returns:
        - 200: PipelineStatusResponse with complete pipeline information
        - 403: Unauthorized (wrong tenant)
        - 404: Pipeline not found
    """
    tenant_id = current_user["tenant_id"]

    # Get pipeline run
    pipeline_run_repo = PipelineRunRepository(session)
    pipeline = await pipeline_run_repo.get_by_id(pipeline_run_id)

    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    # Verify tenant ownership
    if pipeline.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this pipeline")

    # Get all steps
    step_run_repo = PipelineStepRunRepository(session)
    steps = await step_run_repo.get_by_pipeline_run_id(pipeline_run_id)

    # Get artifacts for steps
    artifact_repo = ArtifactRepository(session)
    step_summaries = []
    total_credits = Decimal(0)

    for step in steps:
        # Get artifact if exists
        artifacts = await artifact_repo.get_by_step_run_id(step.id)
        artifact_summary = None
        if artifacts:
            art = artifacts[0]
            artifact_summary = ArtifactSummary(
                id=art.id,
                artifact_type=art.artifact_type,
                status=art.status.value,
                created_at=art.created_at,
            )

        # Get agent run for credits
        agent_run_repo = AgentRunRepository(session)
        agent_runs = await agent_run_repo.get_by_step_run_id(step.id)
        if agent_runs:
            total_credits += Decimal(agent_runs[0].actual_cost_credits)

        step_summaries.append(StepSummary(
            id=step.id,
            step_number=step.step_number,
            step_type=step.step_type.value,
            status=step.status.value,
            started_at=step.started_at,
            completed_at=step.completed_at,
            retry_count=step.retry_count,
            artifact=artifact_summary,
        ))

    return PipelineStatusResponse(
        pipeline_run_id=pipeline.id,
        task_id=pipeline.task_id,
        tenant_id=pipeline.tenant_id,
        status=pipeline.status.value,
        current_step=pipeline.current_step,
        pause_reasons=pipeline.pause_reasons,
        total_credits_consumed=total_credits,
        steps=step_summaries,
        created_at=pipeline.created_at,
        updated_at=pipeline.updated_at,
        paused_at=pipeline.paused_at,
        pause_expires_at=pipeline.pause_expires_at,
        completed_at=pipeline.completed_at,
    )


# AC-2.7.4: Cancel Pipeline Endpoint
@router.post(
    "/{pipeline_run_id}/cancel",
    response_model=CancelPipelineResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel running pipeline",
    description="Cancel a running or paused pipeline (preserves completed work)"
)
async def cancel_pipeline(
    pipeline_run_id: str,
    request: Optional[CancelPipelineRequest] = None,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Cancel pipeline execution.

    Returns:
        - 200: CancellationResultDTO
        - 400: Cannot cancel completed pipeline
        - 403: Unauthorized
        - 404: Pipeline not found
    """
    tenant_id = current_user["tenant_id"]
    user_id = current_user["user_id"]
    reason = request.reason if request else None

    # Initialize repositories
    pipeline_run_repo = PipelineRunRepository(session)
    step_run_repo = PipelineStepRunRepository(session)

    # Execute use case
    use_case = CancelPipeline(
        pipeline_run_repository=pipeline_run_repo,
        step_run_repository=step_run_repo,
        audit_service=None,  # Optional for MVP
    )

    result = await use_case.execute(
        CancelPipelineCommandDTO(
            pipeline_run_id=pipeline_run_id,
            tenant_id=tenant_id,
            user_id=user_id,
            reason=reason,
        )
    )

    if result.is_err():
        error = result.error
        if error.code == "PIPELINE_NOT_FOUND":
            raise HTTPException(status_code=404, detail=error.message)
        elif error.code == "UNAUTHORIZED":
            raise HTTPException(status_code=403, detail=error.message)
        elif error.code == "CANNOT_CANCEL_COMPLETED":
            raise ClientError(error, status_code=400)
        raise ClientError(error)

    dto = result.value
    await session.commit()

    return CancelPipelineResponse(
        pipeline_run_id=dto.pipeline_run_id,
        previous_status=dto.previous_status,
        new_status=dto.new_status,
        steps_completed=dto.steps_completed,
        steps_cancelled=dto.steps_cancelled,
        message=dto.message,
    )


# AC-2.7.5: Resume Pipeline Endpoint
@router.post(
    "/{pipeline_run_id}/resume",
    response_model=ResumePipelineResponse,
    status_code=status.HTTP_200_OK,
    summary="Resume paused pipeline",
    description="Resume a paused pipeline if pause reasons have been resolved"
)
async def resume_pipeline(
    pipeline_run_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Resume paused pipeline.

    Returns:
        - 200: ResumePipelineResponse
        - 400: Cannot resume (unresolved pause reasons or not paused)
        - 403: Unauthorized
        - 404: Pipeline not found
    """
    tenant_id = current_user["tenant_id"]

    # Get pipeline
    pipeline_run_repo = PipelineRunRepository(session)
    pipeline = await pipeline_run_repo.get_by_id(pipeline_run_id)

    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    # Verify tenant ownership
    if pipeline.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this pipeline")

    # Check if paused
    if pipeline.status != PipelineStatus.paused:
        raise ClientError(
            Error(
                code="NOT_PAUSED",
                message=f"Pipeline is not paused (current status: {pipeline.status.value})",
            )
        )

    # Check if can resume
    if not pipeline.can_resume():
        raise ClientError(
            Error(
                code="CANNOT_RESUME",
                message=f"Pipeline has unresolved pause reasons: {', '.join(pipeline.pause_reasons)}",
            )
        )

    # Resume pipeline
    pipeline.status = PipelineStatus.running
    pipeline.paused_at = None
    await pipeline_run_repo.update(pipeline)
    await session.commit()

    logger.info(f"Pipeline {pipeline_run_id} resumed")

    return ResumePipelineResponse(
        pipeline_run_id=pipeline.id,
        status=pipeline.status.value,
        current_step=pipeline.current_step,
        message="Pipeline resumed successfully",
    )


# AC-2.7.7: Get Step Details Endpoint
@router.get(
    "/{pipeline_run_id}/steps/{step_id}",
    response_model=StepDetailsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get step details",
    description="Retrieve detailed information about a specific pipeline step including agent run and artifact"
)
async def get_step_details(
    pipeline_run_id: str,
    step_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Get detailed step information.

    Returns:
        - 200: StepDetailsResponse
        - 403: Unauthorized
        - 404: Step or pipeline not found
    """
    tenant_id = current_user["tenant_id"]

    # Verify pipeline ownership
    pipeline_run_repo = PipelineRunRepository(session)
    pipeline = await pipeline_run_repo.get_by_id(pipeline_run_id)

    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    if pipeline.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this pipeline")

    # Get step
    step_run_repo = PipelineStepRunRepository(session)
    step = await step_run_repo.get_by_id(step_id)

    if not step or step.pipeline_run_id != pipeline_run_id:
        raise HTTPException(status_code=404, detail="Step not found")

    # Get agent run
    agent_run_repo = AgentRunRepository(session)
    agent_runs = await agent_run_repo.get_by_step_run_id(step_id)
    agent_run_details = None
    if agent_runs:
        agent = agent_runs[0]
        agent_run_details = AgentRunDetails(
            id=agent.id,
            agent_type=agent.agent_type.value,
            model=agent.model,
            prompt_tokens=agent.prompt_tokens,
            completion_tokens=agent.completion_tokens,
            estimated_cost_credits=agent.estimated_cost_credits,
            actual_cost_credits=agent.actual_cost_credits,
            started_at=agent.created_at,  # Use created_at as started_at
            completed_at=agent.completed_at,
        )

    # Get artifact
    artifact_repo = ArtifactRepository(session)
    artifacts = await artifact_repo.get_by_step_run_id(step_id)
    artifact_summary = None
    if artifacts:
        art = artifacts[0]
        artifact_summary = ArtifactSummary(
            id=art.id,
            artifact_type=art.artifact_type,
            status=art.status.value,
            created_at=art.created_at,
        )

    return StepDetailsResponse(
        step_id=step.id,
        pipeline_run_id=step.pipeline_run_id,
        step_number=step.step_number,
        step_type=step.step_type.value,
        status=step.status.value,
        retry_count=step.retry_count,
        max_retries=step.max_retries,
        started_at=step.started_at,
        completed_at=step.completed_at,
        input_snapshot=step.input_snapshot,
        agent_run=agent_run_details,
        artifact=artifact_summary,
    )


# AC-2.7.8: Replay Pipeline Endpoint (UC-25)
@router.post(
    "/{pipeline_run_id}/replay",
    status_code=status.HTTP_200_OK,
    summary="Replay pipeline execution",
    description="Replay a failed or completed pipeline from a specific step or from the beginning"
)
async def replay_pipeline(
    pipeline_run_id: str,
    from_step_id: Optional[str] = None,
    preserve_approved_artifacts: bool = True,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Replay pipeline execution (UC-25).

    Allows replaying a pipeline run from a specific step or from the beginning.
    Optionally preserves approved artifacts from the previous run.

    Query Parameters:
        - from_step_id: Optional step ID to replay from (replays entire pipeline if None)
        - preserve_approved_artifacts: Whether to preserve approved artifacts (default True)

    Returns:
        - 200: New pipeline run information
        - 403: Unauthorized
        - 404: Pipeline not found
    """
    from src.app.use_cases.pipeline.replay_pipeline import ReplayPipelineUseCase
    from src.app.use_cases.pipeline.dtos import ReplayPipelineCommandDTO
    from src.adapter.services.unit_of_work import SqlAlchemyUnitOfWork
    from src.app.services.audit_service import AuditService

    tenant_id = current_user["tenant_id"]

    # Create a minimal audit service implementation for this use case
    class SimpleAuditService(AuditService):
        async def log_event(self, event_type, tenant_id, user_id, resource_type, resource_id, metadata=None):
            logger.info(f"Audit: {event_type} - {resource_type}/{resource_id}")

    # Initialize UoW and use case
    uow = SqlAlchemyUnitOfWork(session)
    audit_service = SimpleAuditService()

    use_case = ReplayPipelineUseCase(uow=uow, audit_service=audit_service)

    result = await use_case.execute(
        ReplayPipelineCommandDTO(
            pipeline_run_id=pipeline_run_id,
            tenant_id=tenant_id,
            from_step_id=from_step_id,
            preserve_approved_artifacts=preserve_approved_artifacts,
        )
    )

    if result.is_err():
        error = result.error
        if error.code == "PIPELINE_RUN_NOT_FOUND":
            raise HTTPException(status_code=404, detail=error.message)
        raise ClientError(error)

    return {
        "new_pipeline_run_id": result.value.new_pipeline_run_id,
        "status": result.value.status,
        "started_from_step": result.value.started_from_step,
    }
