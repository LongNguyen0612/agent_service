"""Compensate Credits Use Case - Story 2.5

Handles credit refunds for invalidated or failed pipeline steps.
"""

import logging
from decimal import Decimal
from typing import Optional
from datetime import datetime, timedelta
from libs.result import Result, Return, Error
from src.app.repositories.agent_run_repository import IAgentRunRepository
from src.app.repositories.pipeline_step_repository import IPipelineStepRunRepository
from src.app.services.billing_client import BillingClient, BillingError
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CompensateCreditsCommandDTO(BaseModel):
    """Command DTO for credit compensation"""

    tenant_id: str
    step_run_id: str
    reason: str = "STEP_INVALIDATED"


class CompensateCreditsResponseDTO(BaseModel):
    """Response DTO for credit compensation"""

    refunded: bool
    amount: Decimal
    transaction_id: Optional[str] = None
    message: str


class CompensateCredits:
    """
    Use case for compensating (refunding) credits - AC-2.5.4

    Refunds credits when a pipeline step is invalidated or needs compensation.
    Implements 15-minute automatic refund window per story requirements.
    """

    # 15-minute refund window (in minutes)
    AUTO_REFUND_WINDOW_MINUTES = 15

    def __init__(
        self,
        agent_run_repository: IAgentRunRepository,
        step_run_repository: IPipelineStepRunRepository,
        billing_client: BillingClient,
    ):
        """
        Initialize CompensateCredits use case.

        Args:
            agent_run_repository: Repository for agent runs
            step_run_repository: Repository for pipeline step runs
            billing_client: Client for billing service
        """
        self.agent_run_repository = agent_run_repository
        self.step_run_repository = step_run_repository
        self.billing_client = billing_client

    async def execute(
        self, command: CompensateCreditsCommandDTO
    ) -> Result[CompensateCreditsResponseDTO]:
        """
        Execute credit compensation for an invalidated step.

        Flow:
        1. Get step run and verify it exists
        2. Get agent run to determine credit amount
        3. Check if within 15-minute refund window
        4. Call billing service to refund credits
        5. Return result

        Args:
            command: Command with tenant_id, step_run_id, and reason

        Returns:
            Result[CompensateCreditsResponseDTO]: Compensation result
        """
        # Step 1: Get step run
        step_run = await self.step_run_repository.get_by_id(command.step_run_id)
        if not step_run:
            return Return.err(
                Error(
                    code="STEP_RUN_NOT_FOUND",
                    message=f"Step run {command.step_run_id} not found",
                )
            )

        # Step 2: Get agent run(s) for this step
        agent_runs = await self.agent_run_repository.get_by_step_run_id(command.step_run_id)
        if not agent_runs:
            return Return.err(
                Error(
                    code="NO_AGENT_RUNS_FOUND",
                    message=f"No agent runs found for step {command.step_run_id}",
                )
            )

        # Get the most recent agent run (should only be one per step in MVP)
        agent_run = agent_runs[-1]
        refund_amount = Decimal(str(agent_run.actual_cost_credits))

        # Step 3: Check if within automatic refund window
        if step_run.completed_at:
            time_since_completion = datetime.utcnow() - step_run.completed_at
            if time_since_completion > timedelta(minutes=self.AUTO_REFUND_WINDOW_MINUTES):
                logger.warning(
                    f"Step {command.step_run_id} is outside 15-minute refund window. "
                    f"Manual escalation required."
                )
                return Return.ok(
                    CompensateCreditsResponseDTO(
                        refunded=False,
                        amount=refund_amount,
                        message="Outside automatic refund window - manual escalation required",
                    )
                )

        # Step 4: Refund credits via billing service
        try:
            # Generate idempotency key for refund
            idempotency_key = f"refund:{step_run.pipeline_run_id}:{step_run.id}"

            # Call billing service
            transaction = await self.billing_client.refund_credits(
                tenant_id=command.tenant_id,
                amount=refund_amount,
                idempotency_key=idempotency_key,
                reference_type="pipeline_step_refund",
                reference_id=step_run.id,
                metadata={
                    "original_step_run_id": step_run.id,
                    "pipeline_run_id": step_run.pipeline_run_id,
                    "reason": command.reason,
                    "original_amount": float(refund_amount),
                },
            )

            logger.info(
                f"Successfully refunded {refund_amount} credits for step {command.step_run_id}"
            )

            return Return.ok(
                CompensateCreditsResponseDTO(
                    refunded=True,
                    amount=refund_amount,
                    transaction_id=transaction.transaction_id,
                    message=f"Successfully refunded {refund_amount} credits",
                )
            )

        except BillingError as e:
            logger.error(f"Failed to refund credits for step {command.step_run_id}: {e}")
            # Log for manual review but don't fail the operation
            return Return.ok(
                CompensateCreditsResponseDTO(
                    refunded=False,
                    amount=refund_amount,
                    message=f"Refund failed - logged for manual review: {e.message}",
                )
            )
        except Exception as e:
            logger.error(f"Unexpected error during credit compensation: {e}")
            return Return.err(
                Error(
                    code="COMPENSATION_ERROR",
                    message="Failed to compensate credits",
                    reason=str(e),
                )
            )
