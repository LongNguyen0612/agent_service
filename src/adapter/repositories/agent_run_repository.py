"""Agent Run Repository Implementation - Story 2.4

SQLAlchemy implementation for managing AgentRun entities.
"""
from typing import List, Optional
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from src.app.repositories.agent_run_repository import IAgentRunRepository
from src.domain.agent_run import AgentRun


class AgentRunRepository(IAgentRunRepository):
    """SQLAlchemy implementation of Agent Run repository - Story 2.4, AC-2.4.2"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, agent_run: AgentRun) -> AgentRun:
        """
        Create a new agent run record.

        Args:
            agent_run: AgentRun entity to create

        Returns:
            AgentRun: Created agent run with generated ID
        """
        self.session.add(agent_run)
        await self.session.flush()
        await self.session.refresh(agent_run)
        return agent_run

    async def get_by_id(self, agent_run_id: str) -> Optional[AgentRun]:
        """
        Get agent run by ID.

        Args:
            agent_run_id: ID of the agent run

        Returns:
            Optional[AgentRun]: Agent run if found, None otherwise
        """
        stmt = select(AgentRun).where(AgentRun.id == agent_run_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_step_run_id(self, step_run_id: str) -> List[AgentRun]:
        """
        Get all agent runs for a pipeline step run.

        Args:
            step_run_id: ID of the pipeline step run

        Returns:
            List[AgentRun]: List of agent runs, ordered by created_at
        """
        stmt = (
            select(AgentRun)
            .where(AgentRun.step_run_id == step_run_id)
            .order_by(AgentRun.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_pipeline_run_id(self, pipeline_run_id: str) -> List[AgentRun]:
        """
        Get all agent runs for a pipeline run.

        Args:
            pipeline_run_id: ID of the pipeline run

        Returns:
            List[AgentRun]: List of agent runs, ordered by created_at
        """
        stmt = (
            select(AgentRun)
            .where(AgentRun.pipeline_run_id == pipeline_run_id)
            .order_by(AgentRun.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
