"""Unit tests for RetryWorker - Story 2.5

Tests retry job processing, exponential backoff, dead letter events,
and billing integration during retries.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from src.worker.retry_worker import RetryWorker, STEP_TO_AGENT
from src.domain.retry_job import RetryJob
from src.domain.pipeline_step import PipelineStepRun
from src.domain.pipeline_run import PipelineRun
from src.domain.task import Task
from src.domain.dead_letter_event import DeadLetterEvent
from src.domain.enums import (
    RetryStatus, StepStatus, PipelineStatus, StepType, AgentType,
    ArtifactStatus, PauseReason
)
from src.app.services.agent_executor import AgentExecutionResult
from src.app.services.billing_client import InsufficientCreditsError, BillingServiceUnavailable


@pytest.fixture
def mock_retry_job_repository():
    """Mock retry job repository"""
    repo = MagicMock()
    repo.get_due_jobs = AsyncMock(return_value=[])
    repo.update_status = AsyncMock()
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def mock_step_run_repository():
    """Mock pipeline step run repository"""
    repo = MagicMock()
    repo.get_by_id = AsyncMock()
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def mock_dead_letter_repository():
    """Mock dead letter event repository"""
    repo = MagicMock()
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def mock_pipeline_run_repository():
    """Mock pipeline run repository"""
    repo = MagicMock()
    repo.get_by_id = AsyncMock()
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def mock_task_repository():
    """Mock task repository"""
    repo = MagicMock()
    repo.get_by_id = AsyncMock()
    return repo


@pytest.fixture
def mock_agent_run_repository():
    """Mock agent run repository"""
    repo = MagicMock()
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def mock_artifact_repository():
    """Mock artifact repository"""
    repo = MagicMock()
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def mock_billing_client():
    """Mock billing client"""
    client = MagicMock()
    client.consume_credits = AsyncMock()
    return client


@pytest.fixture
def mock_agent_executor():
    """Mock agent executor"""
    executor = MagicMock()
    executor.execute = AsyncMock(return_value=AgentExecutionResult(
        output={"analysis": "Mock output"},
        prompt_tokens=1000,
        completion_tokens=500,
        estimated_cost_credits=Decimal("50")
    ))
    return executor


@pytest.fixture
def mock_retry_scheduler():
    """Mock retry scheduler"""
    scheduler = MagicMock()
    scheduler.schedule_retry = AsyncMock()
    return scheduler


@pytest.fixture
def retry_worker(
    mock_retry_job_repository,
    mock_step_run_repository,
    mock_dead_letter_repository,
    mock_pipeline_run_repository,
    mock_task_repository,
    mock_agent_run_repository,
    mock_artifact_repository,
    mock_billing_client,
    mock_agent_executor,
    mock_retry_scheduler,
):
    """Create RetryWorker with all mocked dependencies"""
    return RetryWorker(
        retry_job_repository=mock_retry_job_repository,
        step_run_repository=mock_step_run_repository,
        dead_letter_event_repository=mock_dead_letter_repository,
        pipeline_run_repository=mock_pipeline_run_repository,
        task_repository=mock_task_repository,
        agent_run_repository=mock_agent_run_repository,
        artifact_repository=mock_artifact_repository,
        billing_client=mock_billing_client,
        agent_executor=mock_agent_executor,
        retry_scheduler=mock_retry_scheduler,
        poll_interval=1,
    )


@pytest.fixture
def sample_retry_job():
    """Create sample retry job"""
    return RetryJob(
        id="retry-job-1",
        step_run_id="step-run-1",
        retry_attempt=1,
        scheduled_at=datetime.utcnow() - timedelta(seconds=10),
        status=RetryStatus.pending,
    )


@pytest.fixture
def sample_step_run():
    """Create sample pipeline step run"""
    return PipelineStepRun(
        id="step-run-1",
        pipeline_run_id="pipeline-run-1",
        step_number=1,
        step_name="Analysis",
        step_type=StepType.ANALYSIS,
        status=StepStatus.failed,
        retry_count=1,
        max_retries=3,
        input_snapshot={"task_spec": "Build API"},
    )


@pytest.fixture
def sample_pipeline_run():
    """Create sample pipeline run"""
    return PipelineRun(
        id="pipeline-run-1",
        task_id="task-1",
        tenant_id="tenant-1",
        status=PipelineStatus.running,
        current_step=1,
        pause_reasons=[],
    )


@pytest.fixture
def sample_task():
    """Create sample task"""
    task = MagicMock()
    task.id = "task-1"
    task.title = "Build REST API"
    task.input_spec = {"description": "Build API"}
    task.tenant_id = "tenant-1"
    return task


class TestRetryWorkerInit:
    """Tests for RetryWorker initialization"""

    def test_worker_initializes_with_all_dependencies(self, retry_worker):
        """Test worker initializes correctly with all dependencies"""
        assert retry_worker.running is False
        assert retry_worker.poll_interval == 1

    def test_worker_stores_all_repositories(self, retry_worker):
        """Test all repositories are stored"""
        assert retry_worker.retry_job_repository is not None
        assert retry_worker.step_run_repository is not None
        assert retry_worker.dead_letter_event_repository is not None
        assert retry_worker.pipeline_run_repository is not None
        assert retry_worker.task_repository is not None
        assert retry_worker.agent_run_repository is not None
        assert retry_worker.artifact_repository is not None


class TestProcessDueJobs:
    """Tests for _process_due_jobs"""

    @pytest.mark.asyncio
    async def test_process_due_jobs_no_jobs(self, retry_worker):
        """Test processing when no due jobs exist"""
        retry_worker.retry_job_repository.get_due_jobs.return_value = []

        await retry_worker._process_due_jobs()

        retry_worker.retry_job_repository.get_due_jobs.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_due_jobs_with_jobs(
        self, retry_worker, sample_retry_job, sample_step_run
    ):
        """Test processing due jobs"""
        retry_worker.retry_job_repository.get_due_jobs.return_value = [sample_retry_job]
        retry_worker.step_run_repository.get_by_id.return_value = sample_step_run

        # Mock _execute_step_retry to return False (failure)
        with patch.object(retry_worker, '_execute_step_retry', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = False
            await retry_worker._process_due_jobs()

        retry_worker.retry_job_repository.get_due_jobs.assert_called_once()


class TestProcessRetryJob:
    """Tests for _process_retry_job"""

    @pytest.mark.asyncio
    async def test_process_retry_job_step_not_found(
        self, retry_worker, sample_retry_job
    ):
        """Test handling when step run is not found"""
        retry_worker.step_run_repository.get_by_id.return_value = None

        await retry_worker._process_retry_job(sample_retry_job)

        retry_worker.retry_job_repository.update_status.assert_called_with(
            sample_retry_job.id, RetryStatus.failed
        )

    @pytest.mark.asyncio
    async def test_process_retry_job_success(
        self, retry_worker, sample_retry_job, sample_step_run,
        sample_pipeline_run, sample_task
    ):
        """Test successful retry processing"""
        retry_worker.step_run_repository.get_by_id.return_value = sample_step_run
        retry_worker.pipeline_run_repository.get_by_id.return_value = sample_pipeline_run
        retry_worker.task_repository.get_by_id.return_value = sample_task

        await retry_worker._process_retry_job(sample_retry_job)

        # Should mark job as completed on success
        retry_worker.retry_job_repository.update_status.assert_called()


class TestExecuteStepRetry:
    """Tests for _execute_step_retry - Core retry execution logic"""

    @pytest.mark.asyncio
    async def test_execute_step_retry_success(
        self, retry_worker, sample_step_run, sample_pipeline_run, sample_task
    ):
        """Test successful step retry execution - AC-2.5.2"""
        retry_worker.pipeline_run_repository.get_by_id.return_value = sample_pipeline_run
        retry_worker.task_repository.get_by_id.return_value = sample_task

        result = await retry_worker._execute_step_retry(sample_step_run)

        assert result is True
        # Verify agent was executed
        retry_worker.agent_executor.execute.assert_called_once()
        # Verify agent run was created
        retry_worker.agent_run_repository.create.assert_called_once()
        # Verify artifact was created
        retry_worker.artifact_repository.create.assert_called_once()
        # Verify billing was called
        retry_worker.billing_client.consume_credits.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_step_retry_pipeline_not_found(
        self, retry_worker, sample_step_run
    ):
        """Test retry fails when pipeline run not found"""
        retry_worker.pipeline_run_repository.get_by_id.return_value = None

        result = await retry_worker._execute_step_retry(sample_step_run)

        assert result is False

    @pytest.mark.asyncio
    async def test_execute_step_retry_pipeline_cancelled(
        self, retry_worker, sample_step_run, sample_pipeline_run
    ):
        """Test retry skipped when pipeline is cancelled - AC-2.6.4"""
        sample_pipeline_run.status = PipelineStatus.cancelled
        retry_worker.pipeline_run_repository.get_by_id.return_value = sample_pipeline_run

        result = await retry_worker._execute_step_retry(sample_step_run)

        assert result is False
        # Step should be marked as cancelled
        retry_worker.step_run_repository.update.assert_called()

    @pytest.mark.asyncio
    async def test_execute_step_retry_task_not_found(
        self, retry_worker, sample_step_run, sample_pipeline_run
    ):
        """Test retry fails when task not found"""
        retry_worker.pipeline_run_repository.get_by_id.return_value = sample_pipeline_run
        retry_worker.task_repository.get_by_id.return_value = None

        result = await retry_worker._execute_step_retry(sample_step_run)

        assert result is False

    @pytest.mark.asyncio
    async def test_execute_step_retry_agent_execution_fails(
        self, retry_worker, sample_step_run, sample_pipeline_run, sample_task
    ):
        """Test retry fails when agent execution fails"""
        retry_worker.pipeline_run_repository.get_by_id.return_value = sample_pipeline_run
        retry_worker.task_repository.get_by_id.return_value = sample_task
        retry_worker.agent_executor.execute.side_effect = Exception("Agent error")

        result = await retry_worker._execute_step_retry(sample_step_run)

        assert result is False
        # Step should be marked as failed
        retry_worker.step_run_repository.update.assert_called()

    @pytest.mark.asyncio
    async def test_execute_step_retry_insufficient_credits(
        self, retry_worker, sample_step_run, sample_pipeline_run, sample_task
    ):
        """Test retry pauses pipeline on insufficient credits - AC-2.4.3"""
        retry_worker.pipeline_run_repository.get_by_id.return_value = sample_pipeline_run
        retry_worker.task_repository.get_by_id.return_value = sample_task
        retry_worker.billing_client.consume_credits.side_effect = InsufficientCreditsError(
            "Insufficient credits"
        )

        result = await retry_worker._execute_step_retry(sample_step_run)

        # Should still return True (step completed, just billing failed)
        assert result is True
        # Pipeline should be updated with paused status
        retry_worker.pipeline_run_repository.update.assert_called()

    @pytest.mark.asyncio
    async def test_execute_step_retry_billing_unavailable(
        self, retry_worker, sample_step_run, sample_pipeline_run, sample_task
    ):
        """Test retry continues when billing service unavailable"""
        retry_worker.pipeline_run_repository.get_by_id.return_value = sample_pipeline_run
        retry_worker.task_repository.get_by_id.return_value = sample_task
        retry_worker.billing_client.consume_credits.side_effect = BillingServiceUnavailable()

        result = await retry_worker._execute_step_retry(sample_step_run)

        # Should still return True (billing failure doesn't fail the step)
        assert result is True

    @pytest.mark.asyncio
    async def test_execute_step_retry_uses_input_snapshot(
        self, retry_worker, sample_step_run, sample_pipeline_run, sample_task
    ):
        """Test retry uses stored input_snapshot - AC-2.5.2"""
        sample_step_run.input_snapshot = {"custom": "snapshot_data"}
        retry_worker.pipeline_run_repository.get_by_id.return_value = sample_pipeline_run
        retry_worker.task_repository.get_by_id.return_value = sample_task

        await retry_worker._execute_step_retry(sample_step_run)

        # Verify agent was called with input_snapshot
        call_args = retry_worker.agent_executor.execute.call_args
        assert call_args[1]["inputs"] == {"custom": "snapshot_data"}

    @pytest.mark.asyncio
    async def test_execute_step_retry_idempotency_key_format(
        self, retry_worker, sample_step_run, sample_pipeline_run, sample_task
    ):
        """Test retry uses correct idempotency key format - AC-2.5.5"""
        sample_step_run.retry_count = 2
        retry_worker.pipeline_run_repository.get_by_id.return_value = sample_pipeline_run
        retry_worker.task_repository.get_by_id.return_value = sample_task

        await retry_worker._execute_step_retry(sample_step_run)

        # Verify billing was called with retry-specific idempotency key
        call_args = retry_worker.billing_client.consume_credits.call_args
        assert "retry_2" in call_args[1]["idempotency_key"]


class TestCreateDeadLetterEvent:
    """Tests for _create_dead_letter_event"""

    @pytest.mark.asyncio
    async def test_create_dead_letter_event(
        self, retry_worker, sample_step_run
    ):
        """Test dead letter event creation - AC-2.5.3"""
        await retry_worker._create_dead_letter_event(sample_step_run)

        retry_worker.dead_letter_event_repository.create.assert_called_once()
        call_args = retry_worker.dead_letter_event_repository.create.call_args[0][0]
        assert call_args.step_run_id == sample_step_run.id
        assert call_args.failure_reason == "Retries exhausted"
        assert call_args.retry_count == sample_step_run.retry_count


class TestStepToAgentMapping:
    """Tests for step type to agent type mapping"""

    def test_analysis_maps_to_architect(self):
        """Test ANALYSIS step maps to ARCHITECT agent"""
        assert STEP_TO_AGENT[StepType.ANALYSIS] == AgentType.ARCHITECT

    def test_user_stories_maps_to_pm(self):
        """Test USER_STORIES step maps to PM agent"""
        assert STEP_TO_AGENT[StepType.USER_STORIES] == AgentType.PM

    def test_code_skeleton_maps_to_engineer(self):
        """Test CODE_SKELETON step maps to ENGINEER agent"""
        assert STEP_TO_AGENT[StepType.CODE_SKELETON] == AgentType.ENGINEER

    def test_test_cases_maps_to_qa(self):
        """Test TEST_CASES step maps to QA agent"""
        assert STEP_TO_AGENT[StepType.TEST_CASES] == AgentType.QA


class TestWorkerStartStop:
    """Tests for worker start/stop lifecycle"""

    @pytest.mark.asyncio
    async def test_worker_stop(self, retry_worker):
        """Test worker stops correctly"""
        retry_worker.running = True

        await retry_worker.stop()

        assert retry_worker.running is False
