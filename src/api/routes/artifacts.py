"""
Artifact API Routes (UC-27, UC-28, UC-29, UC-32)

Endpoints for managing artifacts: get, approve, reject, archive.
"""
from typing import Any, Dict
from fastapi import APIRouter, Depends, status, BackgroundTasks
from src.api.error import ClientError
from src.api.routes.websocket import manager as ws_manager
from src.app.services.unit_of_work import UnitOfWork
from src.app.services.audit_service import AuditService
from src.depends import get_unit_of_work, get_audit_service, get_current_user
from src.app.use_cases.artifacts import (
    GetArtifactUseCase,
    GetArtifactResponseDTO,
    ApproveArtifactUseCase,
    ApproveArtifactResponseDTO,
    RejectArtifactUseCase,
    RejectArtifactRequestDTO,
    RejectArtifactResponseDTO,
    ArchiveArtifactUseCase,
    ArchiveArtifactResponseDTO,
)


async def broadcast_to_tenant(tenant_id: str, message: Dict[str, Any]) -> None:
    """Helper function to broadcast WebSocket messages to a tenant."""
    await ws_manager.broadcast_to_tenant(message, tenant_id)

router = APIRouter()


@router.get(
    "/artifacts/{artifact_id}",
    response_model=GetArtifactResponseDTO,
    status_code=status.HTTP_200_OK,
)
async def get_artifact(
    artifact_id: str,
    current_user: dict = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """
    Get a single artifact with its content (UC-27).
    Requires authentication.

    Returns artifact details including content for viewing/downloading.
    """
    use_case = GetArtifactUseCase(uow=uow, tenant_id=current_user["tenant_id"])
    result = await use_case.execute(artifact_id)

    if result.is_err():
        if result.error.code == "ARTIFACT_NOT_FOUND":
            raise ClientError(result.error, status_code=status.HTTP_404_NOT_FOUND)
        else:
            raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)

    return result.value


@router.post(
    "/artifacts/{artifact_id}/approve",
    response_model=ApproveArtifactResponseDTO,
    status_code=status.HTTP_200_OK,
)
async def approve_artifact(
    artifact_id: str,
    current_user: dict = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    audit_service: AuditService = Depends(get_audit_service),
):
    """
    Approve an artifact (UC-28).
    Requires authentication.

    Marks an artifact as approved, making it ready for delivery.
    Only draft artifacts can be approved.
    If a pipeline is paused waiting for approval (AC-2.3.2), it will be resumed.
    """
    use_case = ApproveArtifactUseCase(
        uow=uow,
        tenant_id=current_user["tenant_id"],
        user_id=current_user["user_id"],
        audit_service=audit_service,
        websocket_callback=broadcast_to_tenant,
    )
    result = await use_case.execute(artifact_id)

    if result.is_err():
        if result.error.code == "ARTIFACT_NOT_FOUND":
            raise ClientError(result.error, status_code=status.HTTP_404_NOT_FOUND)
        elif result.error.code in [
            "ALREADY_APPROVED",
            "CANNOT_APPROVE_REJECTED",
            "CANNOT_APPROVE_SUPERSEDED",
        ]:
            raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)
        else:
            raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)

    return result.value


@router.post(
    "/artifacts/{artifact_id}/reject",
    response_model=RejectArtifactResponseDTO,
    status_code=status.HTTP_200_OK,
)
async def reject_artifact(
    artifact_id: str,
    request: RejectArtifactRequestDTO,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    audit_service: AuditService = Depends(get_audit_service),
):
    """
    Reject an artifact and optionally trigger regeneration (UC-29).
    Requires authentication.

    Marks an artifact as rejected with optional feedback.
    If regenerate=true, a new pipeline run is queued.
    """
    use_case = RejectArtifactUseCase(
        uow=uow,
        tenant_id=current_user["tenant_id"],
        user_id=current_user["user_id"],
        audit_service=audit_service,
    )
    result = await use_case.execute(artifact_id, request)

    if result.is_err():
        if result.error.code == "ARTIFACT_NOT_FOUND":
            raise ClientError(result.error, status_code=status.HTTP_404_NOT_FOUND)
        elif result.error.code in [
            "ALREADY_REJECTED",
            "CANNOT_REJECT_APPROVED",
            "CANNOT_REJECT_SUPERSEDED",
        ]:
            raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)
        else:
            raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)

    # If regeneration was requested, trigger pipeline in background
    # (The pipeline run was created, but execution needs to be triggered)
    if result.value.new_pipeline_run_id:
        # TODO: Add background task to execute the new pipeline
        pass

    return result.value


@router.post(
    "/artifacts/{artifact_id}/archive",
    response_model=ArchiveArtifactResponseDTO,
    status_code=status.HTTP_200_OK,
)
async def archive_artifact(
    artifact_id: str,
    current_user: dict = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """
    Archive an artifact (UC-32).
    Requires authentication.

    Marks an artifact as superseded. Cannot archive the latest version.
    """
    use_case = ArchiveArtifactUseCase(
        uow=uow,
        tenant_id=current_user["tenant_id"],
    )
    result = await use_case.execute(artifact_id)

    if result.is_err():
        if result.error.code == "ARTIFACT_NOT_FOUND":
            raise ClientError(result.error, status_code=status.HTTP_404_NOT_FOUND)
        elif result.error.code in ["ALREADY_ARCHIVED", "CANNOT_ARCHIVE_LATEST"]:
            raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)
        else:
            raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)

    return result.value
