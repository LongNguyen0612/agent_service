"""
Reject Artifact Use Case (UC-29)

User rejects a generated artifact with feedback and optionally triggers regeneration.
"""
from libs.result import Result, Error, Return
from src.app.services.unit_of_work import UnitOfWork
from src.app.services.audit_service import AuditService
from src.domain.enums import ArtifactStatus, PipelineStatus
from src.domain.pipeline_run import PipelineRun
from .dtos import RejectArtifactRequestDTO, RejectArtifactResponseDTO


class RejectArtifactUseCase:
    """
    Use case: Reject Artifact and Trigger Regeneration (UC-29)

    Marks an artifact as rejected with optional feedback.
    Optionally triggers a new pipeline run for regeneration.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        tenant_id: str,
        user_id: str,
        audit_service: AuditService,
    ):
        self.uow = uow
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.audit_service = audit_service

    async def execute(
        self, artifact_id: str, request: RejectArtifactRequestDTO
    ) -> Result[RejectArtifactResponseDTO]:
        """
        Reject an artifact and optionally trigger regeneration

        Args:
            artifact_id: The artifact ID to reject
            request: Rejection request with feedback and regenerate flag

        Returns:
            Result[RejectArtifactResponseDTO]: Rejection confirmation
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

            # Check if already rejected
            if artifact.status == ArtifactStatus.rejected:
                return Return.err(
                    Error(code="ALREADY_REJECTED", message="Artifact is already rejected")
                )

            # Check if approved
            if artifact.status == ArtifactStatus.approved:
                return Return.err(
                    Error(
                        code="CANNOT_REJECT_APPROVED",
                        message="Cannot reject an approved artifact",
                    )
                )

            # Check if superseded
            if artifact.status == ArtifactStatus.superseded:
                return Return.err(
                    Error(
                        code="CANNOT_REJECT_SUPERSEDED",
                        message="Cannot reject a superseded artifact",
                    )
                )

            # Reject the artifact with feedback
            artifact.reject(feedback=request.feedback)
            await self.uow.artifacts.update(artifact)

            # Optionally trigger regeneration
            new_pipeline_run_id = None
            if request.regenerate:
                # Create a new pipeline run for the task
                new_pipeline_run = PipelineRun(
                    task_id=artifact.task_id,
                    tenant_id=self.tenant_id,
                    status=PipelineStatus.running,
                    current_step=1,
                )
                created_run = await self.uow.pipeline_runs.create(new_pipeline_run)
                new_pipeline_run_id = created_run.id

            await self.uow.commit()

            # Emit audit event
            metadata = {
                "task_id": artifact.task_id,
                "artifact_type": (
                    artifact.artifact_type.value
                    if hasattr(artifact.artifact_type, "value")
                    else artifact.artifact_type
                ),
                "version": artifact.version,
                "feedback": request.feedback,
                "regenerate": request.regenerate,
            }
            if new_pipeline_run_id:
                metadata["new_pipeline_run_id"] = new_pipeline_run_id

            await self.audit_service.log_event(
                event_type="artifact_rejected",
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                resource_type="artifact",
                resource_id=artifact_id,
                metadata=metadata,
            )

            return Return.ok(
                RejectArtifactResponseDTO(
                    id=artifact.id,
                    status=(
                        artifact.status.value
                        if hasattr(artifact.status, "value")
                        else artifact.status
                    ),
                    rejected_at=artifact.rejected_at,
                    new_pipeline_run_id=new_pipeline_run_id,
                )
            )
