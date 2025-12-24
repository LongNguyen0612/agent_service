from typing import Optional, List
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from src.app.repositories import TaskRepository
from src.domain import Task


class SqlAlchemyTaskRepository(TaskRepository):
    """SQLAlchemy implementation of TaskRepository"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, task: Task) -> Task:
        """Create a new task"""
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def get_by_id(self, task_id: str, tenant_id: str) -> Optional[Task]:
        """Get task by ID with tenant isolation"""
        statement = select(Task).where(Task.id == task_id, Task.tenant_id == tenant_id)
        result = await self.session.exec(statement)
        return result.first()

    async def find_by_project_id(
        self, project_id: str, tenant_id: str, status: Optional[str] = None
    ) -> List[Task]:
        """Find all tasks for a project with optional status filter"""
        statement = select(Task).where(Task.project_id == project_id, Task.tenant_id == tenant_id)

        if status is not None:
            statement = statement.where(Task.status == status)

        # Order by created_at descending (newest first)
        statement = statement.order_by(Task.created_at.desc())

        result = await self.session.exec(statement)
        return list(result.all())

    async def update(self, task: Task) -> Task:
        """Update an existing task"""
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)
        return task
