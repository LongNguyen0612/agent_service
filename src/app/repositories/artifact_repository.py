from abc import ABC, abstractmethod
from typing import List, Optional
from src.domain.artifact import Artifact
from src.domain.enums import ArtifactType


class IArtifactRepository(ABC):
    """Interface for Artifact repository"""

    @abstractmethod
    async def create(self, artifact: Artifact) -> Artifact:
        """Create a new artifact"""
        pass

    @abstractmethod
    async def get_by_id(self, artifact_id: str) -> Optional[Artifact]:
        """Get artifact by ID"""
        pass

    @abstractmethod
    async def get_by_task_and_type(
        self, task_id: str, artifact_type: ArtifactType
    ) -> List[Artifact]:
        """Get all artifacts for a task filtered by type, ordered by version"""
        pass

    @abstractmethod
    async def get_max_version(self, task_id: str, artifact_type: ArtifactType) -> int:
        """Get the maximum version number for a task and artifact type"""
        pass

    @abstractmethod
    async def get_by_pipeline_run(self, pipeline_run_id: str) -> List[Artifact]:
        """Get all artifacts for a pipeline run"""
        pass

    @abstractmethod
    async def get_by_step_run_id(self, step_run_id: str) -> List[Artifact]:
        """Get all artifacts for a pipeline step run"""
        pass

    @abstractmethod
    async def get_by_task(self, task_id: str) -> List[Artifact]:
        """Get all artifacts for a task, ordered by creation time"""
        pass

    @abstractmethod
    async def update(self, artifact: Artifact) -> Artifact:
        """Update an existing artifact"""
        pass

    @abstractmethod
    async def get_latest_by_task_and_type(
        self, task_id: str, artifact_type: ArtifactType
    ) -> Optional[Artifact]:
        """Get the latest version of an artifact for a task and type"""
        pass
