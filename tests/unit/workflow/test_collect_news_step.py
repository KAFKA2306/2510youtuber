import threading
from typing import Any, Dict, List

import pytest

from app.workflow.base import StepResult, WorkflowContext
from app.workflow.ports import SyncNewsCollectionAdapter
from app.workflow.steps import CollectNewsStep


class _FakePort:
    def __init__(self, results: List[Dict[str, Any]]):
        self.results = results
        self.calls: List[tuple[str, str]] = []

    async def collect_news(self, prompt: str, mode: str) -> List[Dict[str, Any]]:
        self.calls.append((prompt, mode))
        return list(self.results)


class _ExplodingPort:
    async def collect_news(self, prompt: str, mode: str) -> List[Dict[str, Any]]:  # type: ignore[override]
        raise RuntimeError("network down")


@pytest.mark.asyncio
async def test_collect_news_step_success(monkeypatch):
    monkeypatch.setattr("app.workflow.steps.sheets_manager", None, raising=False)
    context = WorkflowContext(run_id="run-1", mode="daily")
    fake_items = [{"title": "headline", "url": "https://example.com", "summary": "ok", "source": "unit"}]
    port = _FakePort(fake_items)
    step = CollectNewsStep(news_port=port)

    result = await step.execute(context)

    assert isinstance(result, StepResult)
    assert result.success is True
    assert result.data == {"news_items": fake_items, "count": len(fake_items)}
    assert context.get("news_items") == fake_items
    assert len(port.calls) == 1
    recorded_prompt, recorded_mode = port.calls[0]
    assert recorded_mode == "daily"
    assert isinstance(recorded_prompt, str) and recorded_prompt


@pytest.mark.asyncio
async def test_collect_news_step_failure_on_exception(monkeypatch):
    monkeypatch.setattr("app.workflow.steps.sheets_manager", None, raising=False)
    context = WorkflowContext(run_id="run-1", mode="daily")
    step = CollectNewsStep(news_port=_ExplodingPort())

    result = await step.execute(context)

    assert result.success is False
    assert "network down" in result.error


@pytest.mark.asyncio
async def test_sync_adapter_runs_collector_in_background_thread():
    main_thread = threading.get_ident()
    calls: list[tuple[str, str]] = []
    worker_threads: list[int] = []

    def blocking_collector(prompt: str, mode: str) -> List[Dict[str, Any]]:
        calls.append((prompt, mode))
        worker_threads.append(threading.get_ident())
        return [{"title": prompt, "url": "u", "summary": "s", "source": mode}]

    adapter = SyncNewsCollectionAdapter(blocking_collector)
    result = await adapter.collect_news("prompt", "mode")

    assert result[0]["title"] == "prompt"
    assert calls == [("prompt", "mode")]
    assert threading.get_ident() == main_thread
    assert worker_threads and worker_threads[0] != main_thread
