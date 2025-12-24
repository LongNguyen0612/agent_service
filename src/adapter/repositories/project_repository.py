from typing import List, Optional
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from src.app.repositories import ProjectRepository
from src.domain import Project


class SqlAlchemyProjectRepository(ProjectRepository):
    """SQLAlchemy implementation of ProjectRepository"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, project: Project) -> Project:
        """Create a new project"""
        self.session.add(project)
        await self.session.flush()
        await self.session.refresh(project)
        return project

    async def get_by_id(self, project_id: str, tenant_id: str = None) -> Optional[Project]:
        """Get project by ID, optionally filtered by tenant for security"""
        statement = select(Project).where(Project.id == project_id)
        if tenant_id:
            statement = statement.where(Project.tenant_id == tenant_id)
        result = await self.session.exec(statement)
        return result.first()

    async def get_by_tenant_id(self, tenant_id: str) -> List[Project]:
        """Get all projects for a tenant"""
        statement = select(Project).where(Project.tenant_id == tenant_id)
        result = await self.session.exec(statement)
        return list(result.all())

    async def update(self, project: Project) -> Project:
        """Update an existing project"""
        self.session.add(project)
        await self.session.flush()
        await self.session.refresh(project)
        return project
