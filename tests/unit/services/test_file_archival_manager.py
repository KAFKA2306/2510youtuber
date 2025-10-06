import json
from pathlib import Path

import pytest

from app.services.file_archival import FileArchivalManager


pytestmark = pytest.mark.unit


def test_list_archived_workflows_parses_run_id_with_underscores(tmp_path):
    manager = FileArchivalManager(base_output_dir=tmp_path)

    first_dir = Path(
        manager.create_output_directory(
            run_id="local_20250101_123456",
            timestamp="20240101_010101",
            title="Market News: Update",
        )
    )
    manager.create_output_directory(
        run_id="run-002",
        timestamp="20240202_020202",
        title="Daily Recap",
    )

    metadata = json.loads((first_dir / ".archive_meta.json").read_text())
    assert metadata["run_id"] == "local_20250101_123456"
    assert metadata["timestamp"] == "20240101_010101"
    assert metadata["sanitized_title"] == manager.sanitize_title("Market News: Update")

    entries = manager.list_archived_workflows()

    assert [entry["timestamp"] for entry in entries] == ["20240202_020202", "20240101_010101"]
    assert entries[0]["run_id"] == "run-002"
    assert entries[1]["run_id"] == "local_20250101_123456"
    assert entries[1]["title"] == manager.sanitize_title("Market News: Update")
