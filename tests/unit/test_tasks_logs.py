"""Tests for log discovery helpers in scripts.tasks."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pytest

from scripts.tasks import _discover_latest_structured


@pytest.mark.unit
def test_discover_latest_structured_prefers_metadata_timestamp(tmp_path):
    """Latest run should be selected based on metadata timestamps, not file mtime."""

    log_root = tmp_path / "logs"
    runs_root = log_root / "runs"
    runs_root.mkdir(parents=True)

    # Older run with newer file modification time
    old_run = runs_root / "session_old"
    old_run.mkdir()
    (old_run / "events.jsonl").write_text("{}\n", encoding="utf-8")
    (old_run / "workflow.log").write_text("old", encoding="utf-8")
    old_metadata = {
        "session_id": "session_old",
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T01:00:00+00:00",
    }
    (old_run / "metadata.json").write_text(json.dumps(old_metadata), encoding="utf-8")

    # Ensure this run has the most recent file modification timestamp
    now_ts = datetime.now(tz=timezone.utc).timestamp()
    os.utime(old_run / "events.jsonl", (now_ts, now_ts))

    # Newer run synced from elsewhere with older mtime but newer metadata timestamp
    new_run = runs_root / "session_new"
    new_run.mkdir()
    (new_run / "events.jsonl").write_text("{}\n", encoding="utf-8")
    (new_run / "workflow.log").write_text("new", encoding="utf-8")
    new_metadata = {
        "session_id": "session_new",
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-12-31T23:59:59+00:00",
    }
    (new_run / "metadata.json").write_text(json.dumps(new_metadata), encoding="utf-8")

    # Give the new run an older modification time to simulate sync'd files
    older_ts = now_ts - 3600
    os.utime(new_run / "events.jsonl", (older_ts, older_ts))

    discovered = _discover_latest_structured(log_root)

    assert discovered is not None
    assert discovered.parent.name == "session_new"
