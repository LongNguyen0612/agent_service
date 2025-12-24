from sqlmodel.ext.asyncio.session import AsyncSession
from src.app.services.unit_of_work import UnitOfWork
from src.adapter.repositories.project_repository import SqlAlchemyProjectRepository
from src.adapter.repositories.task_repository import SqlAlchemyTaskRepository
from src.adapter.repositories.pipeline_run_repository import PipelineRunRepository
from src.adapter.repositories.pipeline_step_repository import PipelineStepRunRepository
from src.adapter.repositories.artifact_repository import ArtifactRepository
from src.adapter.repositories.export_job_repository import SqlAlchemyExportJobRepository
from src.adapter.repositories.git_sync_job_repository import SqlAlchemyGitSyncJobRepository
from src.adapter.repositories.agent_run_repository import AgentRunRepository


class SqlAlchemyUnitOfWork(UnitOfWork):
    """SQLAlchemy implementation of UnitOfWork pattern"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def __aenter__(self):
        # Initialize all repositories with the session
        self.projects = SqlAlchemyProjectRepository(self.session)
        self.tasks = SqlAlchemyTaskRepository(self.session)
        self.pipeline_runs = PipelineRunRepository(self.session)
        self.pipeline_steps = PipelineStepRunRepository(self.session)
        self.artifacts = ArtifactRepository(self.session)
        self.export_jobs = SqlAlchemyExportJobRepository(self.session)
        self.git_sync_jobs = SqlAlchemyGitSyncJobRepository(self.session)
        self.agent_runs = AgentRunRepository(self.session)
        return self

    async def __aexit__(self, *args):
        await self.rollback()

    async def commit(self):
        await self.session.commit()

    async def rollback(self):
        await self.session.rollback()
