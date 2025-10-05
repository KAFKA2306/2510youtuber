from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Generator

import pytest
from fastapi.testclient import TestClient

from app.gui.api import deps
from app.gui.api.main import create_app
from app.gui.core import settings as settings_module
from app.models.workflow import WorkflowResult


@pytest.fixture(autouse=True)
def override_dependencies(tmp_path: Path) -> Generator[None, None, None]:
    commands_file = tmp_path / "commands.yml"
    commands_file.write_text(
        """
commands:
  - id: quick
    name: Quick
    runner: process
    command:
      - python
      - -c
      - print('ok')
""".strip(),
        encoding="utf-8",
    )
    settings_file = tmp_path / "settings.yml"
    settings_file.write_text(
        """
defaults:
  execution:
    mode: local
    concurrency_limit: 2
  logging:
    verbose: false
    retention_days: 7
  notifications_enabled: false
radios: {}
""".strip(),
        encoding="utf-8",
    )
    state_file = tmp_path / "preferences.yml"
    prompt_db = tmp_path / "prompts.db"
    prompt_store = tmp_path / "prompts"
    execution_log = tmp_path / "execution_log.jsonl"
    metadata_history = tmp_path / "metadata_history.csv"

    workflow_result = WorkflowResult(
        success=True,
        run_id="local_20240101_000000",
        mode="daily",
        execution_time_seconds=120.0,
        video_path="output/video.mp4",
        video_url="https://youtube.com/watch?v=test",
        title="Test Video",
        thumbnail_path="output/thumb.png",
        generated_files=["output/video.mp4", "output/audio.wav", "output/script.txt"],
        wow_score=8.2,
        quality_score=0.9,
        curiosity_gap_score=0.7,
        surprise_points=2,
        emotion_peaks=4,
        visual_instructions=3,
        retention_prediction=55.0,
        japanese_purity=98.5,
        video_review_summary="Looks good",
        video_review_actions=["Adjust intro"],
    )
    execution_log.write_text(workflow_result.model_dump_json() + "\n", encoding="utf-8")
    metadata_history.write_text(
        """timestamp,run_id,mode,title,description,tags,category,thumbnail_text,seo_keywords,target_audience,estimated_watch_time,news_count,news_topics,video_url,view_count,like_count,comment_count,ctr,avg_view_duration
2024-01-01T00:00:00,local_20240101_000000,daily,Test Video,Desc,"[]",News,,"[]",,,0,,https://youtube.com/watch?v=test,1000,50,10,5.0%,180.0s
""".strip(),
        encoding="utf-8",
    )

    deps.get_command_registry.cache_clear()
    deps._get_preferences_store_cached.cache_clear()  # type: ignore[attr-defined]
    deps._get_prompt_engine.cache_clear()  # type: ignore[attr-defined]
    deps.get_prompt_repository.cache_clear()  # type: ignore[attr-defined]
    deps.get_dashboard_service.cache_clear()  # type: ignore[attr-defined]
    deps.DEFAULT_COMMANDS_PATH = commands_file
    deps.DEFAULT_LOG_DIR = tmp_path / "logs"
    deps.DEFAULT_PROMPTS_DB_PATH = prompt_db
    deps.DEFAULT_PROMPTS_BASE_PATH = prompt_store
    deps.DEFAULT_EXECUTION_LOG_PATH = execution_log
    deps.DEFAULT_METADATA_HISTORY_PATH = metadata_history
    deps._JOB_MANAGER = None  # type: ignore[attr-defined]
    settings_module.DEFAULT_SETTINGS_PATH = settings_file
    settings_module.DEFAULT_STATE_PATH = state_file

    yield

    deps.get_command_registry.cache_clear()
    deps._get_preferences_store_cached.cache_clear()  # type: ignore[attr-defined]
    deps._get_prompt_engine.cache_clear()  # type: ignore[attr-defined]
    deps.get_prompt_repository.cache_clear()  # type: ignore[attr-defined]
    deps.get_dashboard_service.cache_clear()  # type: ignore[attr-defined]
    deps._JOB_MANAGER = None  # type: ignore[attr-defined]
    deps.DEFAULT_COMMANDS_PATH = Path("config/gui/commands.yml")
    deps.DEFAULT_LOG_DIR = Path("logs/gui_jobs")
    deps.DEFAULT_PROMPTS_DB_PATH = Path("state/gui/prompts.db")
    deps.DEFAULT_PROMPTS_BASE_PATH = Path("data/prompts")
    deps.DEFAULT_EXECUTION_LOG_PATH = Path("output/execution_log.jsonl")
    deps.DEFAULT_METADATA_HISTORY_PATH = Path("data/metadata_history.csv")
    settings_module.DEFAULT_SETTINGS_PATH = Path("config/gui/settings.yml")
    settings_module.DEFAULT_STATE_PATH = Path("state/gui/preferences.yml")


@pytest.fixture()
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_list_commands(client: TestClient) -> None:
    response = client.get("/commands/")
    assert response.status_code == 200
    data = response.json()
    assert data[0]["id"] == "quick"


def _wait_for_job_completion(client: TestClient, job_id: str, timeout: float = 5.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        if data["status"] in {"succeeded", "failed"}:
            return data
        time.sleep(0.1)
    raise AssertionError("Job did not complete in time")


def test_job_lifecycle(client: TestClient) -> None:
    response = client.post("/jobs/", json={"command_id": "quick", "parameters": {}})
    assert response.status_code == 201
    job_id = response.json()["id"]

    details = _wait_for_job_completion(client, job_id)
    assert details["status"] == "succeeded"

    response = client.get(f"/jobs/{job_id}/logs", params={"tail": 1})
    assert response.status_code == 200
    entries = response.json()["entries"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["job_id"] == job_id
    assert entry["event"] == "job_finished"


def test_job_log_stream(client: TestClient) -> None:
    response = client.post("/jobs/", json={"command_id": "quick", "parameters": {}})
    assert response.status_code == 201
    job_id = response.json()["id"]

    events: list[dict[str, Any]] = []
    with client.websocket_connect(f"/jobs/{job_id}/stream") as websocket:
        while True:
            message = websocket.receive_json()
            events.append(message)
            if message.get("event") == "job_finished":
                break

    assert any(event.get("event") == "job_started" for event in events)
    assert any(event.get("stream") == "stdout" and event.get("message") == "ok" for event in events)
    assert events[-1].get("event") == "job_finished"


def test_settings_roundtrip(client: TestClient) -> None:
    response = client.get("/settings/")
    assert response.status_code == 200

    payload = response.json()["settings"]
    payload["logging"]["verbose"] = True
    response = client.put("/settings/", json=payload)
    assert response.status_code == 200
    assert response.json()["settings"]["logging"]["verbose"] is True


def test_prompt_api(client: TestClient) -> None:
    create_response = client.post(
        "/prompts/intro/versions",
        json=
        {
            "content": "title: Intro\nbody: Hello",
            "message": "initial",
            "author": "tester",
            "tags": ["finance"],
            "name": "Intro Prompt",
            "description": "Main intro prompt",
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["version"] == 1
    assert "Intro" in created["content"]

    list_response = client.get("/prompts/")
    assert list_response.status_code == 200
    prompts = list_response.json()
    assert prompts[0]["id"] == "intro"
    assert prompts[0]["latest_version"] == 1

    detail_response = client.get("/prompts/intro")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["prompt"]["name"] == "Intro Prompt"
    assert detail["latest_version"]["version"] == 1
    assert "body: Hello" in detail["latest_version"]["content"]

    versions_response = client.get("/prompts/intro/versions")
    assert versions_response.status_code == 200
    versions = versions_response.json()
    assert len(versions) == 1
    assert versions[0]["version"] == 1

    version_response = client.get("/prompts/intro/versions/1")
    assert version_response.status_code == 200
    assert "title: Intro" in version_response.json()["content"]


def test_dashboard_artifacts(client: TestClient) -> None:
    response = client.get("/dashboard/artifacts", params={"limit": 5})
    assert response.status_code == 200
    payload = response.json()
    assert payload["artifacts"], "expected at least one artefact group"
    artefact = payload["artifacts"][0]
    assert artefact["run_id"] == "local_20240101_000000"
    assert artefact["video"]["url"].endswith("test")
    assert any(asset["kind"] == "audio" for asset in artefact["audio"])
    assert any(asset["kind"] == "text" for asset in artefact["text"])


def test_dashboard_metrics(client: TestClient) -> None:
    response = client.get("/dashboard/metrics", params={"limit": 5})
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total_runs"] >= 1
    run_metrics = payload["runs"][0]
    assert run_metrics["run_id"] == "local_20240101_000000"
    assert run_metrics["wow_score"] == 8.2
    assert run_metrics["view_count"] == 1000
