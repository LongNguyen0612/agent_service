"""Unit Tests for RunPipelineStep Use Case - Story 2.4

Tests pipeline execution logic with mocked dependencies.
"""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from src.app.use_cases.pipeline import RunPipelineCommandDTO, PipelineStepResultDTO
from src.app.use_cases.pipeline.run_pipeline_step import RunPipelineStep, STEP_TO_AGENT
from src.app.services.billing_client import InsufficientCreditsError
from src.app.services.agent_executor import AgentExecutionResult
from src.domain.task import Task
from src.domain.pipeline_run import PipelineRun
from src.domain.pipeline_step import PipelineStepRun
from src.domain.agent_run import AgentRun
from src.domain.artifact import Artifact
from src.domain.enums import (
    PipelineStatus,
    StepStatus,
    StepType,
    AgentType,
    ArtifactStatus,
    PauseReason,
)


@pytest.fixture
def mock_repositories():
    """Create all mocked repositories"""
    return {
        "task_repo": MagicMock(),
        "pipeline_run_repo": MagicMock(),
        "step_run_repo": MagicMock(),
        "agent_run_repo": MagicMock(),
        "artifact_repo": MagicMock(),
    }


@pytest.fixture
def mock_billing_client():
    """Create mock BillingClient"""
    return MagicMock()


@pytest.fixture
def mock_agent_executor():
    """Create mock AgentExecutor"""
    return MagicMock()


@pytest.fixture
def run_pipeline_step(mock_repositories, mock_billing_client, mock_agent_executor):
    """Create RunPipelineStep use case with mocked dependencies"""
    return RunPipelineStep(
        task_repository=mock_repositories["task_repo"],
        pipeline_run_repository=mock_repositories["pipeline_run_repo"],
        step_run_repository=mock_repositories["step_run_repo"],
        agent_run_repository=mock_repositories["agent_run_repo"],
        artifact_repository=mock_repositories["artifact_repo"],
        billing_client=mock_billing_client,
        agent_executor=mock_agent_executor,
    )


@pytest.fixture
def sample_task():
    """Create sample task for testing"""
    return Task(
        id="task_123",
        project_id="project_xyz",
        tenant_id="tenant_abc",
        title="Build REST API",
        input_spec={"description": "Create a REST API with FastAPI"},
        status="pending",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_pipeline_run(sample_task):
    """Create sample pipeline run"""
    return PipelineRun(
        id="pipeline_abc",
        task_id=sample_task.id,
        tenant_id=sample_task.tenant_id,
        status=PipelineStatus.running,
        current_step=1,
        pause_reasons=[],
        started_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


class TestRunPipelineStep:
    """Unit tests for RunPipelineStep use case - AC-2.4.1 through AC-2.4.5"""

    @pytest.mark.asyncio
    async def test_successful_pipeline_step_execution(
        self,
        run_pipeline_step,
        mock_repositories,
        mock_billing_client,
        mock_agent_executor,
        sample_task,
        sample_pipeline_run,
    ):
        """Test AC-2.4.1, AC-2.4.2, AC-2.4.3: Successful step execution with billing"""
        # Arrange
        mock_repositories["task_repo"].get_by_id = AsyncMock(return_value=sample_task)
        mock_repositories["pipeline_run_repo"].get_by_task_id = AsyncMock(
            return_value=None
        )
        mock_repositories["pipeline_run_repo"].create = AsyncMock(
            return_value=sample_pipeline_run
        )
        mock_repositories["pipeline_run_repo"].get_by_id = AsyncMock(
            return_value=sample_pipeline_run
        )
        mock_repositories["step_run_repo"].create = AsyncMock(
            side_effect=lambda x: x
        )
        mock_repositories["step_run_repo"].update = AsyncMock(
            side_effect=lambda x: x
        )
        mock_repositories["agent_run_repo"].create = AsyncMock(
            side_effect=lambda x: x
        )
        mock_repositories["artifact_repo"].create = AsyncMock(
            side_effect=lambda x: x
        )
        mock_repositories["pipeline_run_repo"].update = AsyncMock(
            side_effect=lambda x: x
        )

        # Mock agent execution
        mock_agent_executor.execute = AsyncMock(
            return_value=AgentExecutionResult(
                output={"analysis": "Mock analysis"},
                prompt_tokens=1500,
                completion_tokens=800,
                estimated_cost_credits=Decimal("50.00"),
            )
        )

        # Mock billing
        mock_billing_client.consume_credits = AsyncMock()

        command = RunPipelineCommandDTO(task_id="task_123", tenant_id="tenant_abc")

        # Act
        result = await run_pipeline_step.execute(command)

        # Assert
        assert result.is_ok()
        dto = result.value
        assert isinstance(dto, PipelineStepResultDTO)
        assert dto.step_number == 1
        assert dto.step_type == StepType.ANALYSIS.value
        assert dto.status == StepStatus.completed.value
        assert dto.artifact_id is not None

        # Verify agent was executed with correct type (AC-2.4.2)
        mock_agent_executor.execute.assert_called_once()
        call_args = mock_agent_executor.execute.call_args
        assert call_args.kwargs["agent_type"] == AgentType.ARCHITECT

        # Verify billing was called (AC-2.4.3)
        mock_billing_client.consume_credits.assert_called_once()
        billing_call = mock_billing_client.consume_credits.call_args
        assert billing_call.kwargs["amount"] == Decimal("50.00")
        assert "pipeline_abc" in billing_call.kwargs["idempotency_key"]

    @pytest.mark.asyncio
    async def test_insufficient_credits_pauses_pipeline(
        self,
        run_pipeline_step,
        mock_repositories,
        mock_billing_client,
        mock_agent_executor,
        sample_task,
        sample_pipeline_run,
    ):
        """Test AC-2.4.3: Insufficient credits pauses pipeline without rollback"""
        # Arrange
        mock_repositories["task_repo"].get_by_id = AsyncMock(return_value=sample_task)
        mock_repositories["pipeline_run_repo"].get_by_task_id = AsyncMock(
            return_value=sample_pipeline_run
        )
        mock_repositories["pipeline_run_repo"].get_by_id = AsyncMock(
            return_value=sample_pipeline_run
        )
        mock_repositories["step_run_repo"].create = AsyncMock(
            side_effect=lambda x: x
        )
        mock_repositories["step_run_repo"].update = AsyncMock(
            side_effect=lambda x: x
        )
        mock_repositories["agent_run_repo"].create = AsyncMock(
            side_effect=lambda x: x
        )
        mock_repositories["artifact_repo"].create = AsyncMock(
            side_effect=lambda x: x
        )
        mock_repositories["pipeline_run_repo"].update = AsyncMock(
            side_effect=lambda x: x
        )

        # Mock agent execution
        mock_agent_executor.execute = AsyncMock(
            return_value=AgentExecutionResult(
                output={"analysis": "Mock analysis"},
                prompt_tokens=1500,
                completion_tokens=800,
                estimated_cost_credits=Decimal("50.00"),
            )
        )

        # Mock billing failure
        mock_billing_client.consume_credits = AsyncMock(
            side_effect=InsufficientCreditsError("Insufficient credits")
        )

        command = RunPipelineCommandDTO(task_id="task_123", tenant_id="tenant_abc")

        # Act
        result = await run_pipeline_step.execute(command)

        # Assert
        assert result.is_ok()
        dto = result.value
        assert dto.status == "paused_insufficient_credits"
        assert dto.artifact_id is not None  # Work NOT rolled back

        # Verify pipeline was paused
        update_calls = mock_repositories["pipeline_run_repo"].update.call_args_list
        paused_run = update_calls[-1][0][0]
        assert paused_run.status == PipelineStatus.paused
        assert PauseReason.INSUFFICIENT_CREDIT.value in paused_run.pause_reasons

    @pytest.mark.asyncio
    async def test_artifact_status_auto_approved_for_analysis(
        self,
        run_pipeline_step,
        mock_repositories,
        mock_billing_client,
        mock_agent_executor,
        sample_task,
        sample_pipeline_run,
    ):
        """Test AC-2.4.4: ANALYSIS artifacts are auto-approved"""
        # Arrange
        mock_repositories["task_repo"].get_by_id = AsyncMock(return_value=sample_task)
        mock_repositories["pipeline_run_repo"].get_by_task_id = AsyncMock(
            return_value=sample_pipeline_run
        )
        mock_repositories["pipeline_run_repo"].get_by_id = AsyncMock(
            return_value=sample_pipeline_run
        )
        mock_repositories["step_run_repo"].create = AsyncMock(
            side_effect=lambda x: x
        )
        mock_repositories["step_run_repo"].update = AsyncMock(
            side_effect=lambda x: x
        )
        mock_repositories["agent_run_repo"].create = AsyncMock(
            side_effect=lambda x: x
        )

        # Capture artifact creation
        created_artifact = None

        async def capture_artifact(artifact):
            nonlocal created_artifact
            created_artifact = artifact
            return artifact

        mock_repositories["artifact_repo"].create = AsyncMock(
            side_effect=capture_artifact
        )
        mock_repositories["pipeline_run_repo"].update = AsyncMock(
            side_effect=lambda x: x
        )

        mock_agent_executor.execute = AsyncMock(
            return_value=AgentExecutionResult(
                output={"analysis": "Mock analysis"},
                prompt_tokens=1500,
                completion_tokens=800,
                estimated_cost_credits=Decimal("50.00"),
            )
        )
        mock_billing_client.consume_credits = AsyncMock()

        command = RunPipelineCommandDTO(task_id="task_123", tenant_id="tenant_abc")

        # Act
        result = await run_pipeline_step.execute(command)

        # Assert
        assert result.is_ok()
        assert created_artifact is not None
        assert created_artifact.status == ArtifactStatus.approved
        assert created_artifact.approved_at is not None

    @pytest.mark.asyncio
    async def test_idempotency_key_format(
        self,
        run_pipeline_step,
        mock_repositories,
        mock_billing_client,
        mock_agent_executor,
        sample_task,
        sample_pipeline_run,
    ):
        """Test AC-2.4.3: Idempotency key format is {pipeline_run_id}:{step_id}"""
        # Arrange
        mock_repositories["task_repo"].get_by_id = AsyncMock(return_value=sample_task)
        mock_repositories["pipeline_run_repo"].get_by_task_id = AsyncMock(
            return_value=sample_pipeline_run
        )
        mock_repositories["pipeline_run_repo"].get_by_id = AsyncMock(
            return_value=sample_pipeline_run
        )
        mock_repositories["step_run_repo"].create = AsyncMock(
            side_effect=lambda x: x
        )
        mock_repositories["step_run_repo"].update = AsyncMock(
            side_effect=lambda x: x
        )
        mock_repositories["agent_run_repo"].create = AsyncMock(
            side_effect=lambda x: x
        )
        mock_repositories["artifact_repo"].create = AsyncMock(
            side_effect=lambda x: x
        )
        mock_repositories["pipeline_run_repo"].update = AsyncMock(
            side_effect=lambda x: x
        )

        mock_agent_executor.execute = AsyncMock(
            return_value=AgentExecutionResult(
                output={"analysis": "Mock"},
                prompt_tokens=1500,
                completion_tokens=800,
                estimated_cost_credits=Decimal("50.00"),
            )
        )
        mock_billing_client.consume_credits = AsyncMock()

        command = RunPipelineCommandDTO(task_id="task_123", tenant_id="tenant_abc")

        # Act
        await run_pipeline_step.execute(command)

        # Assert
        billing_call = mock_billing_client.consume_credits.call_args
        idempotency_key = billing_call.kwargs["idempotency_key"]
        assert ":" in idempotency_key
        parts = idempotency_key.split(":")
        assert len(parts) == 2  # pipeline_run_id:step_id

    @pytest.mark.asyncio
    async def test_input_snapshot_immutability(
        self,
        run_pipeline_step,
        mock_repositories,
        mock_billing_client,
        mock_agent_executor,
        sample_task,
        sample_pipeline_run,
    ):
        """Test AC-2.4.1: Input snapshot is captured and immutable"""
        # Arrange
        captured_step_run = None

        async def capture_step_update(step_run):
            nonlocal captured_step_run
            captured_step_run = step_run
            return step_run

        mock_repositories["task_repo"].get_by_id = AsyncMock(return_value=sample_task)
        mock_repositories["pipeline_run_repo"].get_by_task_id = AsyncMock(
            return_value=sample_pipeline_run
        )
        mock_repositories["step_run_repo"].create = AsyncMock(
            side_effect=lambda x: x
        )
        mock_repositories["step_run_repo"].update = AsyncMock(
            side_effect=capture_step_update
        )
        mock_repositories["agent_run_repo"].create = AsyncMock(
            side_effect=lambda x: x
        )
        mock_repositories["artifact_repo"].create = AsyncMock(
            side_effect=lambda x: x
        )
        mock_repositories["pipeline_run_repo"].update = AsyncMock(
            side_effect=lambda x: x
        )

        mock_agent_executor.execute = AsyncMock(
            return_value=AgentExecutionResult(
                output={"analysis": "Mock"},
                prompt_tokens=1500,
                completion_tokens=800,
                estimated_cost_credits=Decimal("50.00"),
            )
        )
        mock_billing_client.consume_credits = AsyncMock()

        command = RunPipelineCommandDTO(task_id="task_123", tenant_id="tenant_abc")

        # Act
        await run_pipeline_step.execute(command)

        # Assert
        assert captured_step_run is not None
        assert captured_step_run.input_snapshot is not None
        snapshot = captured_step_run.input_snapshot
        assert snapshot["task_id"] == sample_task.id
        assert snapshot["task_title"] == sample_task.title
        assert snapshot["task_input_spec"] == sample_task.input_spec
        assert "snapshot_at" in snapshot

    @pytest.mark.asyncio
    async def test_step_to_agent_mapping(
        self,
        run_pipeline_step,
        mock_repositories,
        mock_billing_client,
        mock_agent_executor,
        sample_task,
    ):
        """Test AC-2.4.2: Agent type correctly mapped to step type"""
        # Test all step-to-agent mappings
        for step_number, expected_step_type in enumerate([
            StepType.ANALYSIS,
            StepType.USER_STORIES,
            StepType.CODE_SKELETON,
            StepType.TEST_CASES,
        ], start=1):
            # Arrange
            pipeline_run = PipelineRun(
                id=f"pipeline_{step_number}",
                task_id=sample_task.id,
                tenant_id=sample_task.tenant_id,
                status=PipelineStatus.running,
                current_step=step_number,
                pause_reasons=[],
                started_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            mock_repositories["task_repo"].get_by_id = AsyncMock(
                return_value=sample_task
            )
            mock_repositories["pipeline_run_repo"].get_by_task_id = AsyncMock(
                return_value=pipeline_run
            )
            mock_repositories["pipeline_run_repo"].get_by_id = AsyncMock(
                return_value=pipeline_run
            )
            mock_repositories["step_run_repo"].create = AsyncMock(
                side_effect=lambda x: x
            )
            mock_repositories["step_run_repo"].update = AsyncMock(
                side_effect=lambda x: x
            )
            mock_repositories["agent_run_repo"].create = AsyncMock(
                side_effect=lambda x: x
            )
            mock_repositories["artifact_repo"].create = AsyncMock(
                side_effect=lambda x: x
            )
            mock_repositories["pipeline_run_repo"].update = AsyncMock(
                side_effect=lambda x: x
            )

            mock_agent_executor.execute = AsyncMock(
                return_value=AgentExecutionResult(
                    output={"result": "Mock"},
                    prompt_tokens=1000,
                    completion_tokens=500,
                    estimated_cost_credits=Decimal("30.00"),
                )
            )
            mock_billing_client.consume_credits = AsyncMock()

            command = RunPipelineCommandDTO(
                task_id="task_123", tenant_id="tenant_abc"
            )

            # Act
            await run_pipeline_step.execute(command)

            # Assert
            expected_agent_type = STEP_TO_AGENT[expected_step_type]
            call_args = mock_agent_executor.execute.call_args
            assert call_args.kwargs["agent_type"] == expected_agent_type

    @pytest.mark.asyncio
    async def test_task_not_found_returns_error(
        self, run_pipeline_step, mock_repositories
    ):
        """Test error handling when task is not found"""
        # Arrange
        mock_repositories["task_repo"].get_by_id = AsyncMock(return_value=None)

        command = RunPipelineCommandDTO(
            task_id="nonexistent", tenant_id="tenant_abc"
        )

        # Act
        result = await run_pipeline_step.execute(command)

        # Assert
        assert result.is_err()
        assert result.error.code == "TASK_NOT_FOUND"
