"""Git Service Interface - UC-31

Abstract interface for Git operations (push to repository).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class GitPushResult:
    """Result of a Git push operation"""
    success: bool
    commit_sha: Optional[str] = None
    error_message: Optional[str] = None


class IGitService(ABC):
    """Interface for Git operations - UC-31"""

    @abstractmethod
    async def push_content(
        self,
        repository_url: str,
        branch: str,
        file_path: str,
        content: str,
        commit_message: str,
    ) -> GitPushResult:
        """
        Push content to a Git repository

        Args:
            repository_url: The Git repository URL (https or ssh)
            branch: Target branch name
            file_path: Path where the file should be created/updated
            content: File content to push
            commit_message: Commit message

        Returns:
            GitPushResult with success status and commit SHA or error
        """
        pass

    @abstractmethod
    async def validate_repository(self, repository_url: str) -> bool:
        """
        Validate that the repository URL is accessible

        Args:
            repository_url: The Git repository URL to validate

        Returns:
            True if repository is accessible, False otherwise
        """
        pass
