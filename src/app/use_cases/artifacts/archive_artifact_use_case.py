"""
Archive Artifact Use Case (UC-32)

Archives superseded artifacts to keep only relevant versions prominent.
"""
from libs.result import Result, Error, Return
from src.app.services.unit_of_work import UnitOfWork
from src.domain.enums import ArtifactStatus
from .dtos import ArchiveArtifactResponseDTO


class ArchiveArtifactUseCase:
    """
    Use case: Archive Old Artifacts (UC-32)

    Marks artifacts as superseded when they're not the latest version.
    Prevents archiving the latest version for a task+type combination.
    """

    def __init__(self, uow: UnitOfWork, tenant_id: str):
        self.uow = uow
        self.tenant_id = tenant_id

    async def execute(self, artifact_id: str) -> Result[ArchiveArtifactResponseDTO]:
        """
        Archive an artifact (mark as superseded)

        Args:
            artifact_id: The artifact ID to archive

        Returns:
            Result[ArchiveArtifactResponseDTO]: Archive confirmation
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

            # Check if already superseded
            if artifact.status == ArtifactStatus.superseded:
                return Return.err(
                    Error(
                        code="ALREADY_ARCHIVED",
                        message="Artifact is already archived",
                    )
                )

            # Check if this is the latest version - cannot archive latest
            latest_artifact = await self.uow.artifacts.get_latest_by_task_and_type(
                artifact.task_id, artifact.artifact_type
            )
            if latest_artifact and latest_artifact.id == artifact.id:
                return Return.err(
                    Error(
                        code="CANNOT_ARCHIVE_LATEST",
                        message="Cannot archive the latest version of an artifact",
                    )
                )

            # Archive the artifact (mark as superseded)
            artifact.status = ArtifactStatus.superseded
            await self.uow.artifacts.update(artifact)
            await self.uow.commit()

            return Return.ok(
                ArchiveArtifactResponseDTO(
                    id=artifact.id,
                    status=(
                        artifact.status.value
                        if hasattr(artifact.status, "value")
                        else artifact.status
                    ),
                )
            )
