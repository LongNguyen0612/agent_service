"""Pipeline Cost Estimator - Story 2.3

Provides advisory cost estimates for pipeline execution.
AC-2.3.4: Hardcoded estimates for MVP.
"""
from decimal import Decimal
from src.domain.enums import StepType


class CostEstimator:
    """
    Estimates pipeline execution costs based on step types.

    Current implementation uses fixed costs for MVP (AC-2.3.4):
    - ANALYSIS: 50 credits
    - USER_STORIES: 30 credits
    - CODE_SKELETON: 40 credits
    - TEST_CASES: 30 credits
    - Total: 150 credits

    Future: Can be enhanced with dynamic pricing based on:
    - Task complexity
    - Model selection (gpt-4 vs gpt-3.5)
    - Input size
    """

    # Hardcoded costs per step type (AC-2.3.4)
    STEP_COSTS = {
        StepType.ANALYSIS: Decimal("50.00"),
        StepType.USER_STORIES: Decimal("30.00"),
        StepType.CODE_SKELETON: Decimal("40.00"),
        StepType.TEST_CASES: Decimal("30.00"),
    }

    def estimate_pipeline_cost(self, task_complexity: str = "medium") -> Decimal:
        """
        Estimate total pipeline cost for all 4 steps.

        Args:
            task_complexity: Task complexity level (currently ignored, reserved for future)

        Returns:
            Decimal: Estimated total cost in credits (150.00 for MVP)

        Note:
            This is an advisory estimate, not a guarantee.
            Actual costs may vary based on:
            - Actual token usage
            - Retries
            - Model performance
        """
        # For MVP, sum all step costs (AC-2.3.4: Total = 150)
        total = sum(self.STEP_COSTS.values())
        return total

    def estimate_step_cost(self, step_type: StepType) -> Decimal:
        """
        Estimate cost for a single step.

        Args:
            step_type: Type of pipeline step

        Returns:
            Decimal: Estimated cost for this step
        """
        return self.STEP_COSTS.get(step_type, Decimal("0.00"))
