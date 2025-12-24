"""Agent Run Repository Interface - Story 2.4

Interface for managing AgentRun entities (AI agent execution tracking).
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from src.domain.agent_run import AgentRun


class IAgentRunRepository(ABC):
    """Interface for AgentRun repository - AC-2.4.2"""

    @abstractmethod
    async def create(self, agent_run: AgentRun) -> AgentRun:
        """
        Create a new agent run record.

        Args:
            agent_run: AgentRun entity to create

        Returns:
            AgentRun: Created agent run with generated ID
        """
        pass

    @abstractmethod
    async def get_by_id(self, agent_run_id: str) -> Optional[AgentRun]:
        """
        Get agent run by ID.

        Args:
            agent_run_id: ID of the agent run

        Returns:
            Optional[AgentRun]: Agent run if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_by_step_run_id(self, step_run_id: str) -> List[AgentRun]:
        """
        Get all agent runs for a pipeline step run.

        Args:
            step_run_id: ID of the pipeline step run

        Returns:
            List[AgentRun]: List of agent runs, ordered by created_at
        """
        pass

    @abstractmethod
    async def get_by_pipeline_run_id(self, pipeline_run_id: str) -> List[AgentRun]:
        """
        Get all agent runs for a pipeline run.

        Args:
            pipeline_run_id: ID of the pipeline run

        Returns:
            List[AgentRun]: List of agent runs, ordered by created_at
        """
        pass
