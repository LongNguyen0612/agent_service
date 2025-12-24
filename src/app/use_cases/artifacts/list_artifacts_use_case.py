"""
List Artifacts Use Case (UC-26)

User views the list of artifacts generated for a task.
"""
from libs.result import Result, Error, Return
from src.app.services.unit_of_work import UnitOfWork
from src.domain.enums import ArtifactStatus
from .dtos import ListArtifactsResponseDTO, ArtifactDTO


class ListArtifactsUseCase:
    """
    Use case: View Generated Artifacts (UC-26)

    Returns all artifacts for a task in creation order.
    Each artifact includes type, status, version, and approval metadata.
    """

    def __init__(self, uow: UnitOfWork, tenant_id: str):
        self.uow = uow
        self.tenant_id = tenant_id

    async def execute(self, task_id: str) -> Result[ListArtifactsResponseDTO]:
        """
        List all artifacts for a task

        Args:
            task_id: The task ID

        Returns:
            Result[ListArtifactsResponseDTO]: List of artifacts for the task
        """
        async with self.uow:
            # Verify task exists and belongs to tenant
            task = await self.uow.tasks.get_by_id(task_id, self.tenant_id)
            if not task:
                return Return.err(Error(code="TASK_NOT_FOUND", message="Task not found"))

            # Get all artifacts for this task
            artifacts = await self.uow.artifacts.get_by_task(task_id)

            # Convert to DTOs
            artifact_dtos = [
                ArtifactDTO(
                    id=artifact.id,
                    artifact_type=artifact.artifact_type.value if hasattr(artifact.artifact_type, 'value') else artifact.artifact_type,
                    version=artifact.version,
                    status=artifact.status.value if hasattr(artifact.status, 'value') else artifact.status,
                    is_approved=artifact.status == ArtifactStatus.approved,
                    created_at=artifact.created_at,
                    approved_at=artifact.approved_at,
                    rejected_at=artifact.rejected_at,
                )
                for artifact in artifacts
            ]

            return Return.ok(ListArtifactsResponseDTO(artifacts=artifact_dtos))
