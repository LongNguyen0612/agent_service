"""Validate Pipeline Use Case - Story 2.3

Validates pipeline preconditions before execution:
- Task exists and belongs to tenant
- Tenant has sufficient credits
"""
import logging
from decimal import Decimal
from libs.result import Result, Return, Error
from src.app.repositories.task_repository import TaskRepository
from src.app.services.billing_client import BillingClient, BillingServiceUnavailable
from src.app.services.cost_estimator import CostEstimator
from .dtos import ValidatePipelineCommandDTO, ValidationResultDTO

logger = logging.getLogger(__name__)


class ValidatePipeline:
    """
    Validates pipeline preconditions before execution.

    Implements AC-2.3.1, AC-2.3.2, AC-2.3.3, AC-2.3.4:
    - Verifies task exists and belongs to tenant
    - Checks credit balance from billing service
    - Estimates pipeline cost
    - Determines eligibility

    Returns:
        Result[ValidationResultDTO]: Validation result with eligibility status
    """

    def __init__(
        self,
        task_repository: TaskRepository,
        billing_client: BillingClient,
        cost_estimator: CostEstimator,
    ):
        """
        Initialize ValidatePipeline use case.

        Args:
            task_repository: Repository for task lookup
            billing_client: Client for billing service integration
            cost_estimator: Service for cost estimation
        """
        self.task_repository = task_repository
        self.billing_client = billing_client
        self.cost_estimator = cost_estimator

    async def execute(
        self, command: ValidatePipelineCommandDTO
    ) -> Result[ValidationResultDTO]:
        """
        Execute pipeline validation.

        Args:
            command: Validation command with task_id and tenant_id

        Returns:
            Result[ValidationResultDTO]: Validation result

        AC-2.3.1: Returns ValidationResultDTO with eligibility status
        AC-2.3.2: Verifies task exists and belongs to tenant
        AC-2.3.3: Retrieves current credit balance
        AC-2.3.4: Estimates pipeline cost (150 credits for MVP)
        """
        try:
            # AC-2.3.2: Verify task exists and belongs to tenant
            task = await self.task_repository.get_by_id(
                task_id=command.task_id, tenant_id=command.tenant_id
            )

            if task is None:
                logger.warning(
                    f"Task validation failed: task_id={command.task_id} not found or access denied"
                )
                return Return.err(
                    Error(
                        code="TASK_NOT_FOUND",
                        message="Task not found or access denied",
                    )
                )

            # AC-2.3.4: Estimate pipeline cost (hardcoded 150 credits for MVP)
            estimated_cost = self.cost_estimator.estimate_pipeline_cost()

            # AC-2.3.3: Get current credit balance from billing service
            try:
                balance_response = await self.billing_client.get_balance(
                    tenant_id=command.tenant_id
                )
                current_balance = balance_response.balance
            except BillingServiceUnavailable as e:
                logger.error(
                    f"Billing service unavailable during validation: {e.message}"
                )
                return Return.err(
                    Error(
                        code="BILLING_SERVICE_UNAVAILABLE",
                        message="Billing service is currently unavailable",
                        reason=str(e),
                    )
                )
            except Exception as e:
                logger.error(f"Error getting balance during validation: {e}")
                return Return.err(
                    Error(
                        code="BALANCE_CHECK_FAILED",
                        message="Failed to check credit balance",
                        reason=str(e),
                    )
                )

            # Compare balance vs estimated cost to determine eligibility
            if current_balance >= estimated_cost:
                logger.info(
                    f"Pipeline validation passed: task_id={command.task_id}, "
                    f"balance={current_balance}, estimated_cost={estimated_cost}"
                )
                return Return.ok(
                    ValidationResultDTO(
                        eligible=True,
                        estimated_cost=estimated_cost,
                        current_balance=current_balance,
                        reason=None,
                    )
                )
            else:
                logger.warning(
                    f"Pipeline validation failed - insufficient credits: task_id={command.task_id}, "
                    f"balance={current_balance}, required={estimated_cost}"
                )
                return Return.ok(
                    ValidationResultDTO(
                        eligible=False,
                        estimated_cost=estimated_cost,
                        current_balance=current_balance,
                        reason=f"Insufficient credits. Required: {estimated_cost}, Available: {current_balance}",
                    )
                )

        except Exception as e:
            logger.error(f"Unexpected error during pipeline validation: {e}")
            return Return.err(
                Error(
                    code="VALIDATION_ERROR",
                    message="An unexpected error occurred during validation",
                    reason=str(e),
                )
            )
