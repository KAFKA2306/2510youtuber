"""File archival and organization system for workflow outputs.

Manages structured storage of generated videos, audio, thumbnails, and scripts.
Ensures files persist after workflow completion with predictable organization.
"""

import logging
import os
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from app.workflow.base import WorkflowContext

logger = logging.getLogger(__name__)


class FileArchivalManager:
    """Manages archival and organization of workflow-generated files.

    Directory structure:
        output/{timestamp}_{run_id}_{sanitized_title}/
            ├── video.mp4
            ├── audio.wav
            ├── thumbnail.png
            ├── script.txt
            └── subtitles.srt
    """

    def __init__(self, base_output_dir: str = "output", retention_days: int = 0):
        """Initialize file archival manager.

        Args:
            base_output_dir: Base directory for archived files (default: "output")
            retention_days: Days to retain files (0 = keep forever)
        """
        self.base_output_dir = base_output_dir
        self.retention_days = retention_days
        self._ensure_base_directory()

    def _ensure_base_directory(self):
        """Ensure base output directory exists."""
        Path(self.base_output_dir).mkdir(parents=True, exist_ok=True)

    def sanitize_title(self, title: str) -> str:
        """Sanitize title for safe filesystem usage.

        Args:
            title: Raw title string

        Returns:
            Sanitized title safe for filesystem paths
        """
        # Remove brackets and special punctuation
        sanitized = re.sub(r'[【】\[\]<>:"/\\|?*]', '', title)
        # Replace remaining problematic chars with underscore
        sanitized = re.sub(r'[^\w\s-]', '_', sanitized)
        # Replace multiple spaces/underscores with single underscore
        sanitized = re.sub(r'[\s_]+', '_', sanitized)
        # Trim and limit length
        sanitized = sanitized.strip('_')[:50]
        return sanitized

    def _get_directory_name(self, run_id: str, timestamp: str, title: str) -> str:
        """Generate directory name for workflow output.

        Args:
            run_id: Workflow run ID
            timestamp: Timestamp string (YYYYMMDD_HHMMSS)
            title: Video title

        Returns:
            Directory name string
        """
        sanitized_title = self.sanitize_title(title)
        return f"{timestamp}_{run_id}_{sanitized_title}"

    def create_output_directory(self, run_id: str, timestamp: str, title: str) -> str:
        """Create output directory for workflow files.

        Args:
            run_id: Workflow run ID
            timestamp: Timestamp string
            title: Video title

        Returns:
            Absolute path to created directory
        """
        dir_name = self._get_directory_name(run_id, timestamp, title)
        output_dir = os.path.join(self.base_output_dir, dir_name)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        logger.info(f"Created output directory: {output_dir}")
        return output_dir

    def get_video_output_path(self, run_id: str, timestamp: str, title: str) -> str:
        """Get output path for video file.

        Args:
            run_id: Workflow run ID
            timestamp: Timestamp string
            title: Video title

        Returns:
            Absolute path for video file
        """
        dir_name = self._get_directory_name(run_id, timestamp, title)
        return os.path.join(self.base_output_dir, dir_name, "video.mp4")

    def get_audio_output_path(self, run_id: str, timestamp: str, title: str) -> str:
        """Get output path for audio file."""
        dir_name = self._get_directory_name(run_id, timestamp, title)
        return os.path.join(self.base_output_dir, dir_name, "audio.wav")

    def get_thumbnail_output_path(self, run_id: str, timestamp: str, title: str) -> str:
        """Get output path for thumbnail file."""
        dir_name = self._get_directory_name(run_id, timestamp, title)
        return os.path.join(self.base_output_dir, dir_name, "thumbnail.png")

    def get_script_output_path(self, run_id: str, timestamp: str, title: str) -> str:
        """Get output path for script file."""
        dir_name = self._get_directory_name(run_id, timestamp, title)
        return os.path.join(self.base_output_dir, dir_name, "script.txt")

    def archive_workflow_files(
        self,
        run_id: str,
        timestamp: str,
        title: str,
        files: Dict[str, str]
    ) -> Dict[str, str]:
        """Archive workflow files to organized directory.

        Args:
            run_id: Workflow run ID
            timestamp: Timestamp string
            title: Video title
            files: Dict mapping file type to source path
                   e.g., {"video": "/tmp/video.mp4", "audio": "/tmp/audio.wav"}

        Returns:
            Dict mapping file type to archived path
        """
        output_dir = self.create_output_directory(run_id, timestamp, title)
        archived = {}

        for file_type, source_path in files.items():
            if not source_path or not os.path.exists(source_path):
                logger.warning(f"Source file not found: {source_path}")
                continue

            # Determine target filename
            if file_type == "video":
                target_name = "video.mp4"
            elif file_type == "audio":
                target_name = "audio.wav"
            elif file_type == "thumbnail":
                target_name = "thumbnail.png"
            elif file_type == "script":
                target_name = "script.txt"
            elif file_type == "subtitle":
                target_name = "subtitles.srt"
            else:
                # Keep original extension
                target_name = f"{file_type}{Path(source_path).suffix}"

            target_path = os.path.join(output_dir, target_name)

            # Copy file to archive (preserve original)
            shutil.copy2(source_path, target_path)
            archived[file_type] = target_path
            logger.info(f"Archived {file_type}: {target_path}")

        return archived

    def get_or_create_workflow_directory(self, context: WorkflowContext) -> str:
        """Get or create output directory from workflow context.

        Args:
            context: Workflow context

        Returns:
            Absolute path to workflow output directory
        """
        # Check if already created
        existing_dir = context.get("output_directory")
        if existing_dir and os.path.exists(existing_dir):
            return existing_dir

        # Create new directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        metadata = context.get("metadata", {})
        title = metadata.get("title", "Untitled")

        output_dir = self.create_output_directory(
            run_id=context.run_id,
            timestamp=timestamp,
            title=title
        )

        # Store in context for reuse
        context.set("output_directory", output_dir)
        context.set("output_timestamp", timestamp)

        return output_dir

    def list_archived_workflows(self) -> List[Dict[str, str]]:
        """List all archived workflow directories.

        Returns:
            List of dicts with workflow metadata:
            [{"run_id": "...", "timestamp": "...", "directory": "..."}, ...]
        """
        archived = []
        base_path = Path(self.base_output_dir)

        if not base_path.exists():
            return archived

        for item in base_path.iterdir():
            if not item.is_dir():
                continue

            # Parse directory name: {timestamp}_{run_id}_{title}
            parts = item.name.split('_', 2)
            if len(parts) >= 2:
                # Handle timestamp format: YYYYMMDD_HHMMSS
                timestamp_parts = parts[0:2]
                timestamp = '_'.join(timestamp_parts) if len(timestamp_parts) == 2 else parts[0]
                run_id = parts[1] if len(parts) > 1 else "unknown"

                archived.append({
                    "run_id": run_id,
                    "timestamp": timestamp,
                    "directory": str(item.absolute()),
                    "name": item.name,
                })

        # Sort by timestamp descending (most recent first)
        archived.sort(key=lambda x: x["timestamp"], reverse=True)
        return archived

    def get_files_to_cleanup(self) -> List[Path]:
        """Get list of files eligible for cleanup based on retention policy.

        Returns:
            List of Path objects for directories older than retention period
        """
        if self.retention_days <= 0:
            return []

        cutoff_time = datetime.now() - timedelta(days=self.retention_days)
        cutoff_timestamp = cutoff_time.timestamp()

        to_cleanup = []
        base_path = Path(self.base_output_dir)

        if not base_path.exists():
            return to_cleanup

        for item in base_path.iterdir():
            if not item.is_dir():
                continue

            # Check modification time
            mtime = os.path.getmtime(item)
            if mtime < cutoff_timestamp:
                to_cleanup.append(item)

        return to_cleanup

    def cleanup_old_files(self, dry_run: bool = True) -> List[str]:
        """Clean up old files based on retention policy.

        Args:
            dry_run: If True, only list files without deleting

        Returns:
            List of directories that were (or would be) deleted
        """
        to_cleanup = self.get_files_to_cleanup()
        deleted = []

        for directory in to_cleanup:
            if dry_run:
                logger.info(f"[DRY RUN] Would delete: {directory}")
                deleted.append(str(directory))
            else:
                try:
                    shutil.rmtree(directory)
                    logger.info(f"Deleted old directory: {directory}")
                    deleted.append(str(directory))
                except Exception as e:
                    logger.error(f"Failed to delete {directory}: {e}")

        return deleted
