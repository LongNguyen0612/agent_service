"""Agent Executor Interface - Story 2.4, Task 2.4.1

Defines the interface for executing AI agents in pipeline steps.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
from decimal import Decimal
from pydantic import BaseModel
from src.domain.enums import AgentType


class AgentExecutionResult(BaseModel):
    """
    Result of agent execution - AC-2.4.2

    Attributes:
        output: Agent output as dictionary (will be stored in Artifact)
        prompt_tokens: Number of tokens in the prompt
        completion_tokens: Number of tokens in the completion
        estimated_cost_credits: Estimated cost in credits for this execution

    Example:
        {
            "output": {"analysis": "System analysis details..."},
            "prompt_tokens": 1500,
            "completion_tokens": 800,
            "estimated_cost_credits": 50
        }
    """
    output: Dict[str, Any]
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_credits: Decimal


class AgentExecutor(ABC):
    """
    Abstract interface for agent execution - AC-2.4.2

    Implementations:
    - MockAgentExecutor: Hardcoded responses for MVP (Story 2.4, Task 2.4.2)
    - OpenAIAgentExecutor: Real OpenAI integration (Future)
    - AnthropicAgentExecutor: Real Anthropic integration (Future)
    """

    @abstractmethod
    async def execute(
        self, agent_type: AgentType, inputs: Dict[str, Any]
    ) -> AgentExecutionResult:
        """
        Execute an AI agent with given inputs.

        Args:
            agent_type: Type of agent to execute (ARCHITECT, PM, ENGINEER, QA)
            inputs: Input data for the agent (e.g., task description, previous outputs)

        Returns:
            AgentExecutionResult: Execution result with output and token usage

        Raises:
            Exception: If agent execution fails

        Example:
            result = await executor.execute(
                agent_type=AgentType.ARCHITECT,
                inputs={"task_description": "Build a REST API"}
            )
            # result.output = {"analysis": "..."}
            # result.prompt_tokens = 1500
            # result.completion_tokens = 800
            # result.estimated_cost_credits = 50
        """
        pass
