"""File Storage Interface - UC-30

Abstract interface for storing and retrieving export files.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional


class FileStorage(ABC):
    """Interface for file storage operations - UC-30"""

    @abstractmethod
    async def upload(self, file_path: str, content: bytes) -> str:
        """
        Upload file content to storage

        Args:
            file_path: The destination path/key for the file
            content: The file content as bytes

        Returns:
            The storage path/key of the uploaded file
        """
        pass

    @abstractmethod
    async def generate_signed_url(
        self, file_path: str, expires_in_seconds: int = 3600
    ) -> tuple[str, datetime]:
        """
        Generate a signed/presigned URL for file download

        Args:
            file_path: The path/key of the file
            expires_in_seconds: URL expiry time in seconds

        Returns:
            Tuple of (signed_url, expiry_datetime)
        """
        pass

    @abstractmethod
    async def delete(self, file_path: str) -> bool:
        """
        Delete a file from storage

        Args:
            file_path: The path/key of the file

        Returns:
            True if deletion was successful
        """
        pass

    @abstractmethod
    async def exists(self, file_path: str) -> bool:
        """
        Check if a file exists in storage

        Args:
            file_path: The path/key of the file

        Returns:
            True if file exists
        """
        pass
