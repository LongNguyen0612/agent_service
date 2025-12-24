"""Unit tests for Pipeline Domain Entities - Story 2.1

Tests all business logic methods and entity behaviors per AC-2.1.1 through AC-2.1.5
"""
import pytest
from datetime import datetime, timedelta
from src.domain.pipeline_run import PipelineRun
from src.domain.pipeline_step import PipelineStepRun
from src.domain.agent_run import AgentRun
from src.domain.artifact import Artifact
from src.domain.retry_job import RetryJob
from src.domain.enums import (
    PipelineStatus,
    StepStatus,
    StepType,
    AgentType,
    ArtifactType,
    ArtifactStatus,
    PauseReason,
    RetryStatus,
)


class TestPipelineRun:
    """Test PipelineRun entity - AC-2.1.1"""

    def test_can_resume_when_no_pause_reasons(self):
        """Test AC-2.1.1: can_resume() returns True when pause_reasons is empty"""
        pipeline_run = PipelineRun(
            task_id="task_123",
            tenant_id="tenant_abc",
            pause_reasons=[]
        )
        assert pipeline_run.can_resume() is True

    def test_can_resume_when_has_pause_reasons(self):
        """Test AC-2.1.1: can_resume() returns False when pause_reasons has items"""
        pipeline_run = PipelineRun(
            task_id="task_123",
            tenant_id="tenant_abc",
            pause_reasons=[PauseReason.REJECTION.value]
        )
        assert pipeline_run.can_resume() is False

    def test_add_pause_reason(self):
        """Test AC-2.1.1: add_pause_reason() adds reason to list"""
        pipeline_run = PipelineRun(
            task_id="task_123",
            tenant_id="tenant_abc",
            pause_reasons=[]
        )
        pipeline_run.add_pause_reason(PauseReason.REJECTION)
        assert PauseReason.REJECTION.value in pipeline_run.pause_reasons
        assert len(pipeline_run.pause_reasons) == 1

    def test_add_pause_reason_no_duplicate(self):
        """Test AC-2.1.1: add_pause_reason() doesn't duplicate existing reason"""
        pipeline_run = PipelineRun(
            task_id="task_123",
            tenant_id="tenant_abc",
            pause_reasons=[PauseReason.REJECTION.value]
        )
        pipeline_run.add_pause_reason(PauseReason.REJECTION)
        assert len(pipeline_run.pause_reasons) == 1

    def test_remove_pause_reason(self):
        """Test AC-2.1.1: remove_pause_reason() removes reason from list"""
        pipeline_run = PipelineRun(
            task_id="task_123",
            tenant_id="tenant_abc",
            pause_reasons=[PauseReason.REJECTION.value]
        )
        pipeline_run.remove_pause_reason(PauseReason.REJECTION)
        assert PauseReason.REJECTION.value not in pipeline_run.pause_reasons
        assert len(pipeline_run.pause_reasons) == 0

    def test_is_expired_when_none(self):
        """Test AC-2.1.1: is_expired() returns False when pause_expires_at is None"""
        pipeline_run = PipelineRun(
            task_id="task_123",
            tenant_id="tenant_abc",
            pause_expires_at=None
        )
        assert pipeline_run.is_expired() is False

    def test_is_expired_when_not_expired(self):
        """Test AC-2.1.1: is_expired() returns False when pause_expires_at is in future"""
        future_time = datetime.utcnow() + timedelta(hours=1)
        pipeline_run = PipelineRun(
            task_id="task_123",
            tenant_id="tenant_abc",
            pause_expires_at=future_time
        )
        assert pipeline_run.is_expired() is False

    def test_is_expired_when_expired(self):
        """Test AC-2.1.1: is_expired() returns True when pause_expires_at is in past"""
        past_time = datetime.utcnow() - timedelta(hours=1)
        pipeline_run = PipelineRun(
            task_id="task_123",
            tenant_id="tenant_abc",
            pause_expires_at=past_time
        )
        assert pipeline_run.is_expired() is True


class TestPipelineStepRun:
    """Test PipelineStepRun entity - AC-2.1.2"""

    def test_is_retryable_when_retryable(self):
        """Test AC-2.1.2: is_retryable() returns True when failed and under max_retries"""
        step_run = PipelineStepRun(
            pipeline_run_id="run_123",
            step_number=1,
            step_name="Step 1",
            step_type=StepType.ANALYSIS,
            status=StepStatus.failed,
            retry_count=2,
            max_retries=3
        )
        assert step_run.is_retryable() is True

    def test_is_retryable_when_max_retries_reached(self):
        """Test AC-2.1.2: is_retryable() returns False when max_retries reached"""
        step_run = PipelineStepRun(
            pipeline_run_id="run_123",
            step_number=1,
            step_name="Step 1",
            step_type=StepType.ANALYSIS,
            status=StepStatus.failed,
            retry_count=3,
            max_retries=3
        )
        assert step_run.is_retryable() is False

    def test_is_retryable_when_not_failed(self):
        """Test AC-2.1.2: is_retryable() returns False when status is not failed"""
        step_run = PipelineStepRun(
            pipeline_run_id="run_123",
            step_number=1,
            step_name="Step 1",
            step_type=StepType.ANALYSIS,
            status=StepStatus.completed,
            retry_count=0,
            max_retries=3
        )
        assert step_run.is_retryable() is False

    def test_increment_retry(self):
        """Test AC-2.1.2: increment_retry() increments retry_count"""
        step_run = PipelineStepRun(
            pipeline_run_id="run_123",
            step_number=1,
            step_name="Step 1",
            step_type=StepType.ANALYSIS,
            retry_count=0,
            max_retries=3
        )
        step_run.increment_retry()
        assert step_run.retry_count == 1


class TestAgentRun:
    """Test AgentRun entity - AC-2.1.3"""

    def test_total_tokens_property(self):
        """Test AC-2.1.3: total_tokens property calculates sum correctly"""
        agent_run = AgentRun(
            step_run_id="step_123",
            agent_type=AgentType.ARCHITECT,
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=200
        )
        assert agent_run.total_tokens == 300

    def test_mark_completed(self):
        """Test AC-2.1.3: mark_completed() sets all token and cost fields"""
        agent_run = AgentRun(
            step_run_id="step_123",
            agent_type=AgentType.ARCHITECT,
            model="gpt-4"
        )
        agent_run.mark_completed(
            prompt_tokens=100,
            completion_tokens=200,
            estimated_cost_credits=50,
            actual_cost_credits=45
        )
        assert agent_run.prompt_tokens == 100
        assert agent_run.completion_tokens == 200
        assert agent_run.estimated_cost_credits == 50
        assert agent_run.actual_cost_credits == 45
        assert agent_run.completed_at is not None


class TestArtifact:
    """Test Artifact entity - AC-2.1.4"""

    def test_approve(self):
        """Test AC-2.1.4: approve() sets status and approved_at"""
        artifact = Artifact(
            step_run_id="step_123",
            artifact_type=ArtifactType.ANALYSIS_REPORT,
            status=ArtifactStatus.draft
        )
        artifact.approve()
        assert artifact.status == ArtifactStatus.approved
        assert artifact.approved_at is not None

    def test_reject(self):
        """Test AC-2.1.4: reject() sets status and rejected_at"""
        artifact = Artifact(
            step_run_id="step_123",
            artifact_type=ArtifactType.USER_STORIES,
            status=ArtifactStatus.draft
        )
        artifact.reject()
        assert artifact.status == ArtifactStatus.rejected
        assert artifact.rejected_at is not None

    def test_supersede(self):
        """Test AC-2.1.4: supersede() sets status and superseded_by"""
        artifact = Artifact(
            step_run_id="step_123",
            artifact_type=ArtifactType.CODE_FILES,
            status=ArtifactStatus.approved
        )
        new_artifact_id = "artifact_new_123"
        artifact.supersede(new_artifact_id)
        assert artifact.status == ArtifactStatus.superseded
        assert artifact.superseded_by == new_artifact_id


class TestRetryJob:
    """Test RetryJob entity - AC-2.1.5"""

    def test_is_ready_when_ready(self):
        """Test AC-2.1.5: is_ready() returns True when pending and scheduled time has passed"""
        past_time = datetime.utcnow() - timedelta(minutes=5)
        retry_job = RetryJob(
            step_run_id="step_123",
            retry_attempt=1,
            scheduled_at=past_time,
            status=RetryStatus.pending
        )
        assert retry_job.is_ready() is True

    def test_is_ready_when_not_ready_future_time(self):
        """Test AC-2.1.5: is_ready() returns False when scheduled time is in future"""
        future_time = datetime.utcnow() + timedelta(minutes=5)
        retry_job = RetryJob(
            step_run_id="step_123",
            retry_attempt=1,
            scheduled_at=future_time,
            status=RetryStatus.pending
        )
        assert retry_job.is_ready() is False

    def test_is_ready_when_not_pending(self):
        """Test AC-2.1.5: is_ready() returns False when status is not pending"""
        past_time = datetime.utcnow() - timedelta(minutes=5)
        retry_job = RetryJob(
            step_run_id="step_123",
            retry_attempt=1,
            scheduled_at=past_time,
            status=RetryStatus.processing
        )
        assert retry_job.is_ready() is False

    def test_mark_completed(self):
        """Test AC-2.1.5: mark_completed() sets status and processed_at"""
        retry_job = RetryJob(
            step_run_id="step_123",
            retry_attempt=1,
            scheduled_at=datetime.utcnow(),
            status=RetryStatus.pending
        )
        retry_job.mark_completed()
        assert retry_job.status == RetryStatus.completed
        assert retry_job.processed_at is not None
