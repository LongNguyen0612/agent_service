"""
Artifact Service - Handles artifact creation, versioning, and storage
"""

import os
from pathlib import Path
from typing import Dict, Any
from src.domain.artifact import Artifact
from src.domain.enums import ArtifactType
from src.app.repositories.artifact_repository import IArtifactRepository


class ArtifactService:
    """
    Service for creating and managing artifacts with automatic versioning

    Features:
    - Auto-increments version numbers per (task_id, artifact_type)
    - Stores artifact content to local filesystem (MVP)
    - Returns Artifact entity for database persistence
    """

    def __init__(self, artifact_repo: IArtifactRepository, storage_root: str = "./artifacts"):
        self.artifact_repo = artifact_repo
        self.storage_root = Path(storage_root)

        # Create storage root directory if it doesn't exist
        self.storage_root.mkdir(parents=True, exist_ok=True)

    async def create_artifact(
        self,
        task_id: str,
        pipeline_run_id: str,
        step_run_id: str,
        artifact_type: ArtifactType,
        content: str,
        metadata: Dict[str, Any] = None,
    ) -> Artifact:
        """
        Create an artifact with automatic versioning and file storage

        Args:
            task_id: ID of the task
            pipeline_run_id: ID of the pipeline run
            step_run_id: ID of the pipeline step run that generated this artifact
            artifact_type: Type of artifact (document, code, etc.)
            content: Artifact content (text)
            metadata: Optional metadata dictionary

        Returns:
            Artifact entity (persisted to database)
        """
        # Get next version number for this (task_id, artifact_type) combination
        max_version = await self.artifact_repo.get_max_version(task_id, artifact_type)
        next_version = max_version + 1

        # Generate file path and store content
        content_url = self._store_content(task_id, artifact_type, next_version, content)

        # Create artifact entity matching the Artifact model schema
        artifact = Artifact(
            task_id=task_id,
            pipeline_run_id=pipeline_run_id,
            step_run_id=step_run_id,
            artifact_type=artifact_type,
            version=next_version,
            content={"text": content, "url": content_url, "metadata": metadata or {}},
        )

        # Persist to database
        created_artifact = await self.artifact_repo.create(artifact)
        return created_artifact

    def _store_content(
        self, task_id: str, artifact_type: ArtifactType, version: int, content: str
    ) -> str:
        """
        Store artifact content to local filesystem

        File structure: {storage_root}/{task_id}/{artifact_type}_v{version}.txt

        Args:
            task_id: Task ID (used as directory name)
            artifact_type: Artifact type (used in filename)
            version: Version number
            content: Content to write

        Returns:
            str: Relative file path (content_url)
        """
        # Create task-specific directory
        task_dir = self.storage_root / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        filename = f"{artifact_type.value}_v{version}.txt"
        file_path = task_dir / filename

        # Write content to file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Return absolute path (for database storage)
        return str(file_path)

    def read_content(self, content_url: str) -> str:
        """
        Read artifact content from filesystem

        Args:
            content_url: Relative file path

        Returns:
            str: Artifact content
        """
        file_path = Path(content_url)

        if not file_path.exists():
            raise FileNotFoundError(f"Artifact file not found: {content_url}")

        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
