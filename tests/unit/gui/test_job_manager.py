from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from app.gui.core.settings import GuiSettings
from app.gui.jobs.manager import JobManager
from app.gui.jobs.registry import Command, CommandRegistry


@pytest.mark.asyncio()
async def test_enqueue_and_run_process(tmp_path: Path) -> None:
    command = Command(
        id="echo",
        name="Echo",
        runner="process",
        command=["python", "-c", "print('hello')"],
    )
    registry = CommandRegistry([command])
    manager = JobManager(registry=registry, log_dir=tmp_path)

    job = await manager.enqueue("echo", {}, settings=GuiSettings())
    assert job.status == "pending"

    # Allow the background task to finish.
    for _ in range(50):
        current = await manager.get(job.id)
        if current.status in {"succeeded", "failed"}:
            break
        await asyncio.sleep(0.1)

    finished = await manager.get(job.id)
    assert finished.status == "succeeded"
    assert finished.exit_code == 0
    assert finished.log_path and finished.log_path.exists()
    contents = finished.log_path.read_text(encoding="utf-8")
    events = [json.loads(line) for line in contents.splitlines() if line]
    assert any(event["message"] == "hello" for event in events if event.get("stream") == "stdout")
    assert any(event.get("event") == "job_finished" for event in events)


@pytest.mark.asyncio()
async def test_concurrency_limit(tmp_path: Path) -> None:
    command = Command(
        id="sleep", name="Sleep", runner="process", command=["python", "-c", "import time; time.sleep(1)"]
    )
    registry = CommandRegistry([command])
    manager = JobManager(registry=registry, log_dir=tmp_path)
    settings = GuiSettings()
    settings.execution.concurrency_limit = 1

    job = await manager.enqueue("sleep", {}, settings=settings)
    assert job.status == "pending"

    with pytest.raises(RuntimeError):
        await manager.enqueue("sleep", {}, settings=settings)

    # Allow cleanup
    for _ in range(20):
        current = await manager.get(job.id)
        if current.status in {"succeeded", "failed"}:
            break
        await asyncio.sleep(0.1)


@pytest.mark.asyncio()
async def test_follow_logs_streams_updates(tmp_path: Path) -> None:
    command = Command(
        id="echo",
        name="Echo",
        runner="process",
        command=["python", "-c", "print('hello')"],
    )
    registry = CommandRegistry([command])
    manager = JobManager(registry=registry, log_dir=tmp_path)

    job = await manager.enqueue("echo", {}, settings=GuiSettings())

    events: list[dict[str, Any]] = []

    async def consume() -> None:
        async for event in manager.follow_logs(job.id):
            events.append(event)

    consumer = asyncio.create_task(consume())

    for _ in range(50):
        current = await manager.get(job.id)
        if current.status in {"succeeded", "failed"}:
            break
        await asyncio.sleep(0.1)

    await asyncio.wait_for(consumer, timeout=2)

    assert any(event.get("event") == "job_started" for event in events)
    assert any(event.get("event") == "job_finished" for event in events)
    assert any(event.get("stream") == "stdout" and event.get("message") == "hello" for event in events)
