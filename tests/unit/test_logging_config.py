"""Tests for the logging configuration utilities."""

import json
import logging
from pathlib import Path

from app.logging_config import get_log_session, setup_logging


def test_setup_logging_creates_structured_files(tmp_path):
    log_dir = tmp_path / "logs"
    session = setup_logging(log_level=logging.INFO, log_dir=str(log_dir), session_id="session_test")

    try:
        root = logging.getLogger()
        root.info(
            "Step completed",
            extra={"event": "step_end", "step": "collect_news", "status": "SUCCESS", "duration": 1.2},
        )
        root.error("Something failed", extra={"step": "collect_news"})
    finally:
        logging.shutdown()

    structured_entries = session.structured_log_path.read_text(encoding="utf-8").strip().splitlines()
    assert structured_entries

    first_entry = json.loads(structured_entries[0])
    assert first_entry["session_id"] == "session_test"
    assert first_entry["event"] == "step_end"
    assert first_entry["step"] == "collect_news"

    metadata = json.loads(session.metadata_path.read_text(encoding="utf-8"))
    assert metadata["session_id"] == "session_test"
    assert Path(metadata["paths"]["structured"]).name == "events.jsonl"


def test_logging_session_status_updates(tmp_path):
    log_dir = tmp_path / "logs"
    session = setup_logging(log_level=logging.INFO, log_dir=str(log_dir), session_id="session_status")
    session.mark_status("succeeded", execution_time_seconds=12.5)

    metadata = json.loads(session.metadata_path.read_text(encoding="utf-8"))
    assert metadata["status"] == "succeeded"
    assert metadata["execution_time_seconds"] == 12.5

    retrieved = get_log_session()
    assert retrieved is session
