"""
Approve Artifact Use Case (UC-28)

User approves a generated artifact, marking it as accepted.
Optionally resumes a paused pipeline if waiting for user approval.
"""
from typing import Optional, Callable, Awaitable, Dict, Any
from libs.result import Result, Error, Return
from src.app.services.unit_of_work import UnitOfWork
from src.app.services.audit_service import AuditService
from src.domain.enums import ArtifactStatus, PipelineStatus, PauseReason
from .dtos import ApproveArtifactResponseDTO


class ApproveArtifactUseCase:
    """
    Use case: Approve Artifact (UC-28)

    Marks an artifact as approved when it's in draft status.
    Emits an audit event on successful approval.
    If a pipeline is paused waiting for user approval, resumes it.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        tenant_id: str,
        user_id: str,
        audit_service: AuditService,
        websocket_callback: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None,
    ):
        self.uow = uow
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.audit_service = audit_service
        self.websocket_callback = websocket_callback

    async def execute(self, artifact_id: str) -> Result[ApproveArtifactResponseDTO]:
        """
        Approve an artifact

        Args:
            artifact_id: The artifact ID to approve

        Returns:
            Result[ApproveArtifactResponseDTO]: Approval confirmation
        """
        async with self.uow:
            # Get artifact by ID
            artifact = await self.uow.artifacts.get_by_id(artifact_id)
            if not artifact:
                return Return.err(
                    Error(code="ARTIFACT_NOT_FOUND", message="Artifact not found")
                )

            # Verify tenant isolation through task ownership
            task = await self.uow.tasks.get_by_id(artifact.task_id, self.tenant_id)
            if not task:
                return Return.err(
                    Error(code="ARTIFACT_NOT_FOUND", message="Artifact not found")
                )

            # Check if already approved
            if artifact.status == ArtifactStatus.approved:
                return Return.err(
                    Error(code="ALREADY_APPROVED", message="Artifact is already approved")
                )

            # Check if rejected
            if artifact.status == ArtifactStatus.rejected:
                return Return.err(
                    Error(
                        code="CANNOT_APPROVE_REJECTED",
                        message="Cannot approve a rejected artifact",
                    )
                )

            # Check if superseded
            if artifact.status == ArtifactStatus.superseded:
                return Return.err(
                    Error(
                        code="CANNOT_APPROVE_SUPERSEDED",
                        message="Cannot approve a superseded artifact",
                    )
                )

            # Approve the artifact
            artifact.approve()
            await self.uow.artifacts.update(artifact)

            # Check if there's a paused pipeline waiting for approval
            pipeline_run_id = None
            pipeline_resumed = False
            pipeline_run = await self.uow.pipeline_runs.get_by_id(artifact.pipeline_run_id)

            if pipeline_run and pipeline_run.status == PipelineStatus.paused:
                if PauseReason.AWAITING_USER_APPROVAL.value in pipeline_run.pause_reasons:
                    # Remove the approval pause reason
                    pipeline_run.remove_pause_reason(PauseReason.AWAITING_USER_APPROVAL)

                    # If no more pause reasons, resume the pipeline
                    if pipeline_run.can_resume():
                        pipeline_run.status = PipelineStatus.running
                        pipeline_run.paused_at = None
                        pipeline_resumed = True

                    await self.uow.pipeline_runs.update(pipeline_run)
                    pipeline_run_id = pipeline_run.id

            await self.uow.commit()

            # Emit audit event
            await self.audit_service.log_event(
                event_type="artifact_approved",
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                resource_type="artifact",
                resource_id=artifact_id,
                metadata={
                    "task_id": artifact.task_id,
                    "artifact_type": (
                        artifact.artifact_type.value
                        if hasattr(artifact.artifact_type, "value")
                        else artifact.artifact_type
                    ),
                    "version": artifact.version,
                    "pipeline_resumed": pipeline_resumed,
                    "pipeline_run_id": pipeline_run_id,
                },
            )

            # Emit audit event for pipeline resume if applicable
            if pipeline_resumed and pipeline_run_id:
                await self.audit_service.log_event(
                    event_type="pipeline_resumed",
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    resource_type="pipeline_run",
                    resource_id=pipeline_run_id,
                    metadata={
                        "task_id": artifact.task_id,
                        "artifact_id": artifact_id,
                        "reason": "artifact_approved",
                    },
                )

            # Send WebSocket notification
            if self.websocket_callback:
                await self.websocket_callback(
                    self.tenant_id,
                    {
                        "event": "artifact:approved",
                        "data": {
                            "artifact_id": artifact.id,
                            "artifact_type": (
                                artifact.artifact_type.value
                                if hasattr(artifact.artifact_type, "value")
                                else artifact.artifact_type
                            ),
                            "status": (
                                artifact.status.value
                                if hasattr(artifact.status, "value")
                                else artifact.status
                            ),
                            "pipeline_run_id": pipeline_run_id,
                            "pipeline_resumed": pipeline_resumed,
                            "task_id": artifact.task_id,
                        },
                    },
                )

            return Return.ok(
                ApproveArtifactResponseDTO(
                    id=artifact.id,
                    status=(
                        artifact.status.value
                        if hasattr(artifact.status, "value")
                        else artifact.status
                    ),
                    approved_at=artifact.approved_at,
                    pipeline_run_id=pipeline_run_id,
                    pipeline_resumed=pipeline_resumed,
                )
            )
