from enum import Enum


class ProjectStatus(str, Enum):
    active = "active"
    archived = "archived"


class TaskStatus(str, Enum):
    draft = "draft"
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class PipelineStatus(str, Enum):
    """Status of a pipeline run - AC-2.1.1"""
    running = "running"
    paused = "paused"
    completed = "completed"
    cancelled = "cancelled"
    cancelled_due_to_inactivity = "cancelled_due_to_inactivity"
    failed = "failed"


class StepStatus(str, Enum):
    """Status of a pipeline step run - AC-2.1.2"""
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    invalidated = "invalidated"
    cancelled = "cancelled"


class StepType(str, Enum):
    """Type of pipeline step - AC-2.1.2"""
    ANALYSIS = "ANALYSIS"
    USER_STORIES = "USER_STORIES"
    CODE_SKELETON = "CODE_SKELETON"
    TEST_CASES = "TEST_CASES"


class AgentType(str, Enum):
    """Type of AI agent - AC-2.1.3"""
    ARCHITECT = "ARCHITECT"
    PM = "PM"
    ENGINEER = "ENGINEER"
    QA = "QA"


class ArtifactType(str, Enum):
    """Type of artifact produced by pipeline step - AC-2.1.4"""
    ANALYSIS_REPORT = "ANALYSIS_REPORT"
    USER_STORIES = "USER_STORIES"
    CODE_FILES = "CODE_FILES"
    TEST_SUITE = "TEST_SUITE"
    document = "document"
    code = "code"


class ArtifactStatus(str, Enum):
    """Status of an artifact - AC-2.1.4"""
    draft = "draft"
    approved = "approved"
    rejected = "rejected"
    superseded = "superseded"


class PauseReason(str, Enum):
    """Reason why pipeline is paused - AC-2.1.1"""
    REJECTION = "REJECTION"
    INSUFFICIENT_CREDIT = "INSUFFICIENT_CREDIT"
    AWAITING_USER_APPROVAL = "AWAITING_USER_APPROVAL"


class RetryStatus(str, Enum):
    """Status of retry job - AC-2.1.5"""
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class ExportJobStatus(str, Enum):
    """Status of an export job - UC-30"""
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class GitSyncJobStatus(str, Enum):
    """Status of a Git sync job - UC-31"""
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


# Legacy aliases for backward compatibility
PipelineRunStatus = PipelineStatus
PipelineStepStatus = StepStatus
