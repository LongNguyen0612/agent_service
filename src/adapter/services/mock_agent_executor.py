"""Mock Agent Executor - Story 2.4, Task 2.4.2

Provides hardcoded agent responses for MVP testing.
"""
from typing import Dict, Any
from decimal import Decimal
from src.app.services.agent_executor import AgentExecutor, AgentExecutionResult
from src.domain.enums import AgentType


class MockAgentExecutor(AgentExecutor):
    """
    Mock implementation of AgentExecutor for MVP - AC-2.4.2

    Returns hardcoded responses for each agent type with realistic token counts
    and costs matching the CostEstimator estimates.

    Token counts are simulated to match realistic LLM usage:
    - ARCHITECT (ANALYSIS): ~2300 tokens total, 50 credits
    - PM (USER_STORIES): ~1500 tokens total, 30 credits
    - ENGINEER (CODE_SKELETON): ~2000 tokens total, 40 credits
    - QA (TEST_CASES): ~1500 tokens total, 30 credits
    """

    async def execute(
        self, agent_type: AgentType, inputs: Dict[str, Any]
    ) -> AgentExecutionResult:
        """
        Execute mock agent and return hardcoded response.

        Args:
            agent_type: Type of agent to execute
            inputs: Input data (used in output for context)

        Returns:
            AgentExecutionResult: Mock result with hardcoded output and token usage
        """
        # Get task description from inputs for realistic mock output
        task_desc = inputs.get("task_description", "Unknown task")

        if agent_type == AgentType.ARCHITECT:
            # AC-2.4.2: ANALYSIS step returns analysis output
            return AgentExecutionResult(
                output={
                    "analysis": f"Mock analysis for: {task_desc}",
                    "technical_requirements": [
                        "RESTful API with FastAPI",
                        "PostgreSQL database",
                        "JWT authentication",
                    ],
                    "architecture_decisions": [
                        "Use clean architecture with 4 layers",
                        "Implement repository pattern",
                        "Use async/await for I/O operations",
                    ],
                    "estimated_complexity": "medium",
                },
                prompt_tokens=1500,
                completion_tokens=800,
                estimated_cost_credits=Decimal("50.00"),
            )

        elif agent_type == AgentType.PM:
            # AC-2.4.2: USER_STORIES step returns stories array
            return AgentExecutionResult(
                output={
                    "stories": [
                        {
                            "id": 1,
                            "title": "As a user, I want to create an account",
                            "description": "User registration endpoint",
                            "acceptance_criteria": [
                                "POST /api/users endpoint",
                                "Email validation",
                                "Password hashing",
                            ],
                        },
                        {
                            "id": 2,
                            "title": "As a user, I want to log in",
                            "description": "User authentication endpoint",
                            "acceptance_criteria": [
                                "POST /api/auth/login endpoint",
                                "JWT token generation",
                                "Refresh token support",
                            ],
                        },
                    ]
                },
                prompt_tokens=1000,
                completion_tokens=500,
                estimated_cost_credits=Decimal("30.00"),
            )

        elif agent_type == AgentType.ENGINEER:
            # CODE_SKELETON step returns code structure
            return AgentExecutionResult(
                output={
                    "code_skeleton": {
                        "files": [
                            {
                                "path": "src/domain/user.py",
                                "content": "# User entity\nclass User:\n    pass",
                            },
                            {
                                "path": "src/api/routes/users.py",
                                "content": "# User routes\n@router.post('/users')\nasync def create_user():\n    pass",
                            },
                        ],
                        "dependencies": ["fastapi", "sqlalchemy", "pydantic"],
                    }
                },
                prompt_tokens=1300,
                completion_tokens=700,
                estimated_cost_credits=Decimal("40.00"),
            )

        elif agent_type == AgentType.QA:
            # TEST_CASES step returns test specifications
            return AgentExecutionResult(
                output={
                    "test_cases": [
                        {
                            "name": "test_create_user_success",
                            "description": "Test successful user creation",
                            "steps": [
                                "POST /api/users with valid data",
                                "Assert 201 status code",
                                "Assert user ID returned",
                            ],
                        },
                        {
                            "name": "test_create_user_duplicate_email",
                            "description": "Test duplicate email validation",
                            "steps": [
                                "Create user with email",
                                "POST same email again",
                                "Assert 409 status code",
                            ],
                        },
                    ],
                    "coverage_targets": {
                        "line_coverage": 80,
                        "branch_coverage": 75,
                    },
                },
                prompt_tokens=1000,
                completion_tokens=500,
                estimated_cost_credits=Decimal("30.00"),
            )

        else:
            # Unknown agent type - should not happen in normal flow
            raise ValueError(f"Unknown agent type: {agent_type}")
