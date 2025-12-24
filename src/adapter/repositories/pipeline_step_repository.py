from typing import List, Optional
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from src.app.repositories.pipeline_step_repository import IPipelineStepRunRepository
from src.domain.pipeline_step import PipelineStepRun


class PipelineStepRunRepository(IPipelineStepRunRepository):
    """SQLAlchemy implementation of Pipeline Step Run repository - Story 2.4"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, pipeline_step: PipelineStepRun) -> PipelineStepRun:
        """Create a new pipeline step run"""
        self.session.add(pipeline_step)
        await self.session.flush()
        await self.session.refresh(pipeline_step)
        return pipeline_step

    async def get_by_id(self, step_id: str) -> Optional[PipelineStepRun]:
        """Get pipeline step run by ID"""
        stmt = select(PipelineStepRun).where(PipelineStepRun.id == step_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_pipeline_run_id(self, pipeline_run_id: str) -> List[PipelineStepRun]:
        """Get all step runs for a pipeline run, ordered by step_number"""
        stmt = (
            select(PipelineStepRun)
            .where(PipelineStepRun.pipeline_run_id == pipeline_run_id)
            .order_by(PipelineStepRun.step_number.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, pipeline_step: PipelineStepRun) -> PipelineStepRun:
        """Update an existing pipeline step run"""
        self.session.add(pipeline_step)
        await self.session.flush()
        await self.session.refresh(pipeline_step)
        return pipeline_step


# Alias for backward compatibility with tests
PipelineStepRepository = PipelineStepRunRepository
