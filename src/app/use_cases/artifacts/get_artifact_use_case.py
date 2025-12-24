"""
Get Artifact Use Case (UC-27)

User views a single artifact with its content.
"""
from libs.result import Result, Error, Return
from src.app.services.unit_of_work import UnitOfWork
from .dtos import GetArtifactResponseDTO


class GetArtifactUseCase:
    """
    Use case: Get Single Artifact (UC-27)

    Returns a single artifact with its content.
    Ensures tenant isolation by validating artifact ownership through task.
    """

    def __init__(self, uow: UnitOfWork, tenant_id: str):
        self.uow = uow
        self.tenant_id = tenant_id

    async def execute(self, artifact_id: str) -> Result[GetArtifactResponseDTO]:
        """
        Get a single artifact by ID

        Args:
            artifact_id: The artifact ID

        Returns:
            Result[GetArtifactResponseDTO]: Artifact details with content
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
                # Return 404 for security - don't reveal artifact exists
                return Return.err(
                    Error(code="ARTIFACT_NOT_FOUND", message="Artifact not found")
                )

            # Convert to DTO with content
            return Return.ok(
                GetArtifactResponseDTO(
                    id=artifact.id,
                    task_id=artifact.task_id,
                    artifact_type=(
                        artifact.artifact_type.value
                        if hasattr(artifact.artifact_type, "value")
                        else artifact.artifact_type
                    ),
                    version=artifact.version,
                    status=(
                        artifact.status.value
                        if hasattr(artifact.status, "value")
                        else artifact.status
                    ),
                    content=artifact.content,
                    created_at=artifact.created_at,
                    approved_at=artifact.approved_at,
                    rejected_at=artifact.rejected_at,
                )
            )
