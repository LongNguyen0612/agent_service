"""Local File Storage Adapter - UC-30

Local filesystem implementation for development and testing.
"""
import os
import aiofiles
from datetime import datetime, timedelta
from pathlib import Path
from src.app.services.file_storage import FileStorage


class LocalFileStorage(FileStorage):
    """Local filesystem storage implementation - UC-30"""

    def __init__(self, base_path: str, base_url: str = "http://localhost:8000/files"):
        """
        Initialize local file storage

        Args:
            base_path: Base directory for file storage
            base_url: Base URL for generating download links
        """
        self.base_path = Path(base_path)
        self.base_url = base_url.rstrip("/")
        # Ensure base directory exists
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def upload(self, file_path: str, content: bytes) -> str:
        """Upload file content to local storage"""
        full_path = self.base_path / file_path
        # Ensure parent directory exists
        full_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(full_path, "wb") as f:
            await f.write(content)

        return file_path

    async def generate_signed_url(
        self, file_path: str, expires_in_seconds: int = 3600
    ) -> tuple[str, datetime]:
        """
        Generate a download URL for local files

        Note: For local storage, this generates a simple URL without actual signing.
        In production, use S3 or similar with real signed URLs.
        """
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in_seconds)
        # For local development, generate simple download URL
        url = f"{self.base_url}/{file_path}"
        return url, expires_at

    async def delete(self, file_path: str) -> bool:
        """Delete a file from local storage"""
        full_path = self.base_path / file_path
        try:
            if full_path.exists():
                os.remove(full_path)
            return True
        except OSError:
            return False

    async def exists(self, file_path: str) -> bool:
        """Check if a file exists in local storage"""
        full_path = self.base_path / file_path
        return full_path.exists()
