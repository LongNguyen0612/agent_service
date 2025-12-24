"""Process Export Job Use Case - UC-30

Processes a pending export job by generating a ZIP file of approved artifacts.
"""
import io
import json
import zipfile
from datetime import datetime
from libs.result import Result, Error, Return
from src.app.services.unit_of_work import UnitOfWork
from src.app.services.file_storage import FileStorage
from src.domain.enums import ArtifactStatus, ExportJobStatus


class ProcessExportJobUseCase:
    """
    Use case: Process Export Job (UC-30)

    Processes a pending export job by:
    1. Collecting all approved artifacts for the project
    2. Organizing them by type into a ZIP structure
    3. Uploading the ZIP to storage
    4. Generating a download URL
    """

    def __init__(
        self,
        uow: UnitOfWork,
        file_storage: FileStorage,
        url_expiry_seconds: int = 3600
    ):
        self.uow = uow
        self.file_storage = file_storage
        self.url_expiry_seconds = url_expiry_seconds

    async def execute(self, job_id: str) -> Result[bool]:
        """
        Process an export job

        Args:
            job_id: The export job ID to process

        Returns:
            Result[bool]: True if successful
        """
        async with self.uow:
            # Get the export job
            export_job = await self.uow.export_jobs.get_by_id(job_id)
            if not export_job:
                return Return.err(Error(
                    code="EXPORT_JOB_NOT_FOUND",
                    message="Export job not found"
                ))

            # Check job status
            if export_job.status != ExportJobStatus.pending:
                return Return.err(Error(
                    code="INVALID_JOB_STATUS",
                    message=f"Job status is {export_job.status}, expected pending"
                ))

            # Mark as processing
            export_job.start_processing()
            await self.uow.export_jobs.update(export_job)
            await self.uow.commit()

        # Process outside of transaction to avoid long-running transactions
        try:
            zip_content = await self._generate_zip(export_job.project_id, export_job.tenant_id)

            # Upload to storage
            file_path = f"exports/{export_job.tenant_id}/{export_job.project_id}/{export_job.id}.zip"
            await self.file_storage.upload(file_path, zip_content)

            # Generate signed URL
            download_url, expires_at = await self.file_storage.generate_signed_url(
                file_path, self.url_expiry_seconds
            )

            # Mark as completed
            async with self.uow:
                export_job = await self.uow.export_jobs.get_by_id(job_id)
                export_job.complete(file_path, download_url, expires_at)
                await self.uow.export_jobs.update(export_job)
                await self.uow.commit()

            return Return.ok(True)

        except Exception as e:
            # Mark as failed
            async with self.uow:
                export_job = await self.uow.export_jobs.get_by_id(job_id)
                export_job.fail(str(e))
                await self.uow.export_jobs.update(export_job)
                await self.uow.commit()

            return Return.err(Error(
                code="EXPORT_FAILED",
                message=str(e)
            ))

    async def _generate_zip(self, project_id: str, tenant_id: str) -> bytes:
        """
        Generate ZIP content from approved artifacts

        Returns:
            bytes: ZIP file content
        """
        zip_buffer = io.BytesIO()

        async with self.uow:
            # Get project info for the ZIP root folder name
            project = await self.uow.projects.get_by_id(project_id, tenant_id)
            project_name = project.name if project else "project"
            # Sanitize project name for filesystem
            safe_project_name = "".join(c for c in project_name if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_project_name = safe_project_name.replace(' ', '_')

            # Get all tasks for the project
            tasks = await self.uow.tasks.get_by_project_id(project_id, tenant_id)

            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for task in tasks:
                    # Get approved artifacts for this task
                    artifacts = await self.uow.artifacts.get_by_task(task.id)

                    for artifact in artifacts:
                        if artifact.status != ArtifactStatus.approved:
                            continue

                        # Determine file path in ZIP based on artifact type
                        artifact_type = artifact.artifact_type.value if hasattr(artifact.artifact_type, 'value') else artifact.artifact_type
                        task_folder = task.title.replace(' ', '_')[:50]  # Sanitize task name

                        # Create folder structure: project/artifact_type/task/
                        base_path = f"{safe_project_name}/{artifact_type}/{task_folder}"

                        # Add artifact content to ZIP
                        if artifact.content:
                            # Handle different content structures
                            if isinstance(artifact.content, dict):
                                if "files" in artifact.content:
                                    # Multiple files in artifact
                                    for idx, file_data in enumerate(artifact.content["files"]):
                                        filename = file_data.get("filename", f"file_{idx}.txt")
                                        content = file_data.get("content", "")
                                        file_path = f"{base_path}/{filename}"
                                        zip_file.writestr(file_path, content)
                                else:
                                    # Single content dict - serialize as JSON
                                    filename = f"artifact_v{artifact.version}.json"
                                    file_path = f"{base_path}/{filename}"
                                    content_str = json.dumps(artifact.content, indent=2)
                                    zip_file.writestr(file_path, content_str)
                            else:
                                # String content
                                filename = f"artifact_v{artifact.version}.txt"
                                file_path = f"{base_path}/{filename}"
                                zip_file.writestr(file_path, str(artifact.content))

                # Add manifest file
                manifest = {
                    "project_id": project_id,
                    "project_name": project_name,
                    "exported_at": datetime.utcnow().isoformat(),
                    "task_count": len(tasks),
                }
                zip_file.writestr(
                    f"{safe_project_name}/manifest.json",
                    json.dumps(manifest, indent=2)
                )

        return zip_buffer.getvalue()
