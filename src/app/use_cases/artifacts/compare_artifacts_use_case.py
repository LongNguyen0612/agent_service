from libs.result import Result, Error, Return
from src.app.services.unit_of_work import UnitOfWork
from src.domain.enums import ArtifactType
from .dtos import ArtifactComparisonResponseDTO, ArtifactVersionDTO


class CompareArtifactsUseCase:
    """
    Use case: Compare Artifact Versions (UC-16 / Story 4.2)

    Retrieves all versions of artifacts for a given task and artifact type,
    sorted by version number in ascending order.
    """

    def __init__(self, uow: UnitOfWork, tenant_id: str):
        self.uow = uow
        self.tenant_id = tenant_id

    async def execute(
        self, task_id: str, artifact_type: str
    ) -> Result[ArtifactComparisonResponseDTO]:
        """
        Compare artifact versions for a task

        Args:
            task_id: The task ID
            artifact_type: Type of artifacts to compare (document, code, test, model)

        Returns:
            Result[ArtifactComparisonResponseDTO]: List of artifact versions sorted by version
        """
        async with self.uow:
            # Verify task exists
            task = await self.uow.tasks.get_by_id(task_id, self.tenant_id)
            if not task:
                return Return.err(Error(code="TASK_NOT_FOUND", message="Task not found"))

            # Validate artifact_type
            try:
                artifact_type_enum = ArtifactType(artifact_type)
            except ValueError:
                return Return.err(
                    Error(
                        code="INVALID_ARTIFACT_TYPE",
                        message=f"Invalid artifact type: {artifact_type}. "
                        f"Must be one of: {', '.join([t.value for t in ArtifactType])}",
                    )
                )

            # Get all artifacts for this task and type
            artifacts = await self.uow.artifacts.get_by_task_and_type(task_id, artifact_type_enum)

            # Convert to DTOs (already sorted by version in ascending order from repository)
            version_dtos = [
                ArtifactVersionDTO(
                    id=artifact.id,
                    version=artifact.version,
                    pipeline_run_id=artifact.pipeline_run_id,
                    step_run_id=artifact.step_run_id,
                    created_at=artifact.created_at,
                )
                for artifact in artifacts
            ]

            response = ArtifactComparisonResponseDTO(
                task_id=task_id,
                artifact_type=artifact_type,
                versions=version_dtos,
            )

            return Return.ok(response)
