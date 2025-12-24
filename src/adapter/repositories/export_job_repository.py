from typing import List, Optional
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from src.app.repositories.export_job_repository import IExportJobRepository
from src.domain.export_job import ExportJob
from src.domain.enums import ExportJobStatus


class SqlAlchemyExportJobRepository(IExportJobRepository):
    """SQLAlchemy implementation of ExportJob repository - UC-30"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, export_job: ExportJob) -> ExportJob:
        """Create a new export job"""
        self.session.add(export_job)
        await self.session.flush()
        await self.session.refresh(export_job)
        return export_job

    async def get_by_id(self, job_id: str, tenant_id: str = None) -> Optional[ExportJob]:
        """Get export job by ID, optionally filtered by tenant for security"""
        stmt = select(ExportJob).where(ExportJob.id == job_id)
        if tenant_id:
            stmt = stmt.where(ExportJob.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_project(self, project_id: str, tenant_id: str) -> List[ExportJob]:
        """Get all export jobs for a project"""
        stmt = (
            select(ExportJob)
            .where(ExportJob.project_id == project_id, ExportJob.tenant_id == tenant_id)
            .order_by(ExportJob.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, export_job: ExportJob) -> ExportJob:
        """Update an existing export job"""
        self.session.add(export_job)
        await self.session.flush()
        await self.session.refresh(export_job)
        return export_job

    async def get_pending_jobs(self, limit: int = 10) -> List[ExportJob]:
        """Get pending export jobs for processing"""
        stmt = (
            select(ExportJob)
            .where(ExportJob.status == ExportJobStatus.pending)
            .order_by(ExportJob.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
