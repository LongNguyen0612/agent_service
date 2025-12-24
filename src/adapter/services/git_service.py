"""Git Service Adapter - UC-31

Implementation of Git operations using subprocess/git commands.
For production, this can be enhanced to use GitHub API or GitPython.
"""
import asyncio
import logging
import tempfile
import os
from typing import Optional
from src.app.services.git_service import IGitService, GitPushResult

logger = logging.getLogger(__name__)


class GitService(IGitService):
    """
    Git service implementation using subprocess commands.

    This implementation:
    1. Clones the repository to a temp directory
    2. Creates/updates the file
    3. Commits and pushes the changes
    4. Cleans up the temp directory

    For GitHub repositories, you can also use the GitHub API.
    """

    def __init__(self, git_credentials: Optional[str] = None):
        """
        Initialize GitService

        Args:
            git_credentials: Optional credentials for Git operations
                            Format: "username:token" for HTTPS
                            For SSH, use SSH keys configured on the system
        """
        self.git_credentials = git_credentials

    async def _run_command(
        self, cmd: list[str], cwd: Optional[str] = None
    ) -> tuple[int, str, str]:
        """Run a shell command asynchronously"""
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return process.returncode, stdout.decode(), stderr.decode()

    def _inject_credentials(self, repository_url: str) -> str:
        """Inject credentials into HTTPS repository URL"""
        if not self.git_credentials:
            return repository_url

        if repository_url.startswith("https://"):
            # Insert credentials: https://user:token@github.com/...
            return repository_url.replace(
                "https://", f"https://{self.git_credentials}@"
            )
        return repository_url

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
        temp_dir = None
        try:
            # Create temp directory
            temp_dir = tempfile.mkdtemp(prefix="git_sync_")
            logger.info(f"[GitService] Created temp directory: {temp_dir}")

            # Inject credentials if available
            auth_url = self._inject_credentials(repository_url)

            # Clone the repository
            returncode, stdout, stderr = await self._run_command(
                ["git", "clone", "--depth", "1", "--branch", branch, auth_url, temp_dir]
            )
            if returncode != 0:
                # Try cloning without branch (branch might not exist)
                returncode, stdout, stderr = await self._run_command(
                    ["git", "clone", "--depth", "1", auth_url, temp_dir]
                )
                if returncode != 0:
                    return GitPushResult(
                        success=False,
                        error_message=f"Failed to clone repository: {stderr}",
                    )

                # Create and checkout the branch
                returncode, stdout, stderr = await self._run_command(
                    ["git", "checkout", "-b", branch], cwd=temp_dir
                )
                if returncode != 0:
                    return GitPushResult(
                        success=False,
                        error_message=f"Failed to create branch: {stderr}",
                    )

            # Create directory structure if needed
            full_file_path = os.path.join(temp_dir, file_path)
            os.makedirs(os.path.dirname(full_file_path), exist_ok=True)

            # Write the file
            with open(full_file_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"[GitService] Wrote file: {file_path}")

            # Configure git user (required for commit)
            await self._run_command(
                ["git", "config", "user.email", "superagent@example.com"], cwd=temp_dir
            )
            await self._run_command(
                ["git", "config", "user.name", "Super Agent"], cwd=temp_dir
            )

            # Stage the file
            returncode, stdout, stderr = await self._run_command(
                ["git", "add", file_path], cwd=temp_dir
            )
            if returncode != 0:
                return GitPushResult(
                    success=False, error_message=f"Failed to stage file: {stderr}"
                )

            # Commit
            returncode, stdout, stderr = await self._run_command(
                ["git", "commit", "-m", commit_message], cwd=temp_dir
            )
            if returncode != 0:
                # Check if there's nothing to commit
                if "nothing to commit" in stderr or "nothing to commit" in stdout:
                    return GitPushResult(
                        success=False,
                        error_message="No changes to commit (file unchanged)",
                    )
                return GitPushResult(
                    success=False, error_message=f"Failed to commit: {stderr}"
                )

            # Get commit SHA
            returncode, commit_sha, stderr = await self._run_command(
                ["git", "rev-parse", "HEAD"], cwd=temp_dir
            )
            commit_sha = commit_sha.strip()

            # Push
            returncode, stdout, stderr = await self._run_command(
                ["git", "push", "-u", "origin", branch], cwd=temp_dir
            )
            if returncode != 0:
                return GitPushResult(
                    success=False, error_message=f"Failed to push: {stderr}"
                )

            logger.info(f"[GitService] Successfully pushed to {repository_url}:{branch}")
            return GitPushResult(success=True, commit_sha=commit_sha)

        except Exception as e:
            logger.error(f"[GitService] Error during Git push: {e}")
            return GitPushResult(success=False, error_message=str(e))

        finally:
            # Cleanup temp directory
            if temp_dir and os.path.exists(temp_dir):
                import shutil

                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.info(f"[GitService] Cleaned up temp directory: {temp_dir}")

    async def validate_repository(self, repository_url: str) -> bool:
        """
        Validate that the repository URL is accessible

        Args:
            repository_url: The Git repository URL to validate

        Returns:
            True if repository is accessible, False otherwise
        """
        try:
            auth_url = self._inject_credentials(repository_url)
            returncode, stdout, stderr = await self._run_command(
                ["git", "ls-remote", "--exit-code", auth_url]
            )
            return returncode == 0
        except Exception as e:
            logger.error(f"[GitService] Repository validation failed: {e}")
            return False


class MockGitService(IGitService):
    """
    Mock Git service for testing.

    Always succeeds and returns a fake commit SHA.
    """

    async def push_content(
        self,
        repository_url: str,
        branch: str,
        file_path: str,
        content: str,
        commit_message: str,
    ) -> GitPushResult:
        """Mock push - always succeeds"""
        import hashlib

        # Generate a fake commit SHA based on content
        fake_sha = hashlib.sha1(content.encode()).hexdigest()
        logger.info(
            f"[MockGitService] Simulated push to {repository_url}:{branch}/{file_path}"
        )
        return GitPushResult(success=True, commit_sha=fake_sha)

    async def validate_repository(self, repository_url: str) -> bool:
        """Mock validation - always returns True"""
        return True
