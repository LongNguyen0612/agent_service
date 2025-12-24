"""Agent Run Entity - AC-2.1.3

Tracks individual AI agent invocations with token usage and cost tracking.
"""
from datetime import datetime
from typing import Optional
from sqlmodel import Field
from src.domain.base import BaseModel, generate_uuid
from src.domain.enums import AgentType


class AgentRun(BaseModel, table=True):
    """
    AgentRun Entity - AC-2.1.3

    Tracks AI agent executions including token usage, estimated costs,
    and actual billed costs from the billing service.
    """
    __tablename__ = "agent_runs"

    # Primary identifier
    id: str = Field(default_factory=generate_uuid, primary_key=True)

    # Foreign key to step run
    step_run_id: str = Field(
        foreign_key="pipeline_step_runs.id",
        index=True,
        nullable=False
    )

    # Agent configuration
    agent_type: AgentType = Field(nullable=False, index=True)
    model: str = Field(nullable=False)

    # Token usage tracking
    prompt_tokens: int = Field(default=0, nullable=False)
    completion_tokens: int = Field(default=0, nullable=False)

    # Cost tracking (in credits)
    estimated_cost_credits: int = Field(default=0, nullable=False)
    actual_cost_credits: int = Field(default=0, nullable=False)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    completed_at: Optional[datetime] = Field(default=None)

    class Config:
        use_enum_values = True

    def mark_completed(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        estimated_cost_credits: int,
        actual_cost_credits: int
    ) -> None:
        """Mark agent run as completed with token and cost information"""
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.estimated_cost_credits = estimated_cost_credits
        self.actual_cost_credits = actual_cost_credits
        self.completed_at = datetime.utcnow()

    @property
    def total_tokens(self) -> int:
        """Calculate total tokens used"""
        return self.prompt_tokens + self.completion_tokens
