from typing import List, Optional
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from src.app.repositories.pipeline_run_repository import IPipelineRunRepository
from src.domain.pipeline_run import PipelineRun


class PipelineRunRepository(IPipelineRunRepository):
    """SQLAlchemy implementation of Pipeline Run repository"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, pipeline_run: PipelineRun) -> PipelineRun:
        """Create a new pipeline run"""
        self.session.add(pipeline_run)
        await self.session.flush()
        await self.session.refresh(pipeline_run)
        return pipeline_run

    async def get_by_id(self, pipeline_run_id: str) -> Optional[PipelineRun]:
        """Get pipeline run by ID"""
        stmt = select(PipelineRun).where(PipelineRun.id == pipeline_run_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_task_id(self, task_id: str) -> Optional[PipelineRun]:
        """Get the most recent pipeline run for a task"""
        stmt = (
            select(PipelineRun)
            .where(PipelineRun.task_id == task_id)
            .order_by(PipelineRun.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_all_by_task_id(self, task_id: str) -> List[PipelineRun]:
        """Get all pipeline runs for a task, ordered by created_at desc"""
        stmt = (
            select(PipelineRun)
            .where(PipelineRun.task_id == task_id)
            .order_by(PipelineRun.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, pipeline_run: PipelineRun) -> PipelineRun:
        """Update an existing pipeline run"""
        self.session.add(pipeline_run)
        await self.session.flush()
        await self.session.refresh(pipeline_run)
        return pipeline_run
