from typing import List, Optional
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func
from src.app.repositories.artifact_repository import IArtifactRepository
from src.domain.artifact import Artifact
from src.domain.enums import ArtifactType


class ArtifactRepository(IArtifactRepository):
    """SQLAlchemy implementation of Artifact repository"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, artifact: Artifact) -> Artifact:
        """Create a new artifact"""
        self.session.add(artifact)
        await self.session.flush()
        await self.session.refresh(artifact)
        return artifact

    async def get_by_id(self, artifact_id: str) -> Optional[Artifact]:
        """Get artifact by ID"""
        stmt = select(Artifact).where(Artifact.id == artifact_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_task_and_type(
        self, task_id: str, artifact_type: ArtifactType
    ) -> List[Artifact]:
        """Get all artifacts for a task filtered by type, ordered by version ascending"""
        stmt = (
            select(Artifact)
            .where(Artifact.task_id == task_id, Artifact.artifact_type == artifact_type)
            .order_by(Artifact.version.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_max_version(self, task_id: str, artifact_type: ArtifactType) -> int:
        """Get the maximum version number for a task and artifact type"""
        stmt = select(func.max(Artifact.version)).where(
            Artifact.task_id == task_id, Artifact.artifact_type == artifact_type
        )
        result = await self.session.execute(stmt)
        max_version = result.scalar()
        return max_version if max_version is not None else 0

    async def get_by_pipeline_run(self, pipeline_run_id: str) -> List[Artifact]:
        """Get all artifacts for a pipeline run"""
        stmt = (
            select(Artifact)
            .where(Artifact.pipeline_run_id == pipeline_run_id)
            .order_by(Artifact.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_step_run_id(self, step_run_id: str) -> List[Artifact]:
        """Get all artifacts for a pipeline step run"""
        stmt = (
            select(Artifact)
            .where(Artifact.step_run_id == step_run_id)
            .order_by(Artifact.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_task(self, task_id: str) -> List[Artifact]:
        """Get all artifacts for a task, ordered by creation time"""
        stmt = (
            select(Artifact)
            .where(Artifact.task_id == task_id)
            .order_by(Artifact.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, artifact: Artifact) -> Artifact:
        """Update an existing artifact"""
        self.session.add(artifact)
        await self.session.flush()
        await self.session.refresh(artifact)
        return artifact

    async def get_latest_by_task_and_type(
        self, task_id: str, artifact_type: ArtifactType
    ) -> Optional[Artifact]:
        """Get the latest version of an artifact for a task and type"""
        stmt = (
            select(Artifact)
            .where(Artifact.task_id == task_id, Artifact.artifact_type == artifact_type)
            .order_by(Artifact.version.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
