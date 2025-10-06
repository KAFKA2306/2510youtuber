import os
import re
import tempfile
from pathlib import Path

from app.config.paths import ProjectPaths


class FileUtils:
    @staticmethod
    def ensure_directory(path: str | Path) -> str:
        resolved = ProjectPaths.resolve_relative(str(path))
        resolved.mkdir(parents=True, exist_ok=True)
        return str(resolved)

    @staticmethod
    def safe_filename(filename: str, max_length: int = 100) -> str:
        safe_name = re.sub(r'[<>:"/\\|?*]', "_", filename)
        safe_name = re.sub(r"\s+", "_", safe_name)
        safe_name = safe_name.strip("._")
        if len(safe_name) > max_length:
            name, ext = os.path.splitext(safe_name)
            safe_name = name[: max_length - len(ext)] + ext
        return safe_name or "untitled"

    @staticmethod
    def get_temp_file(prefix: str = "temp_", suffix: str = ".tmp") -> str:
        temp_dir = ProjectPaths.TEMP_DIR
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_file = tempfile.NamedTemporaryFile(suffix=suffix, prefix=prefix, dir=str(temp_dir), delete=False)
        temp_path = temp_file.name
        temp_file.close()
        return temp_path
