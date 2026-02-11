"""Tests for the asynchronous Discord notifier implementation."""
import asyncio
from typing import Any, Dict, List
import httpx
import pytest
from app.discord import DiscordNotifier
class _DummyResponse:
    def raise_for_status(self) -> None:
        return None
class _TrackingClient:
    def __init__(self, tracker: List[Dict[str, Any]]):
        self._tracker = tracker
    async def __aenter__(self) -> "_TrackingClient":
        return self
    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None
    async def post(self, url: str, json: Dict[str, Any]) -> _DummyResponse:
        self._tracker.append({"url": url, "payload": json})
        return _DummyResponse()
class _ErroringClient:
    async def __aenter__(self) -> "_ErroringClient":
        return self
    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None
    async def post(self, url: str, json: Dict[str, Any]) -> _DummyResponse:
        request = httpx.Request("POST", url)
        response = httpx.Response(500, request=request, text="failure")
        raise httpx.HTTPStatusError("boom", request=request, response=response)
@pytest.mark.asyncio
async def test_notify_returns_false_when_disabled() -> None:
    notifier = DiscordNotifier(webhook_url="", client_factory=lambda: _TrackingClient([]))
    assert notifier.enabled is False
    result = await notifier.notify("hello")
    assert result is False
@pytest.mark.asyncio
async def test_notify_uses_async_client_factory() -> None:
    tracker: List[Dict[str, Any]] = []
    notifier = DiscordNotifier(
        webhook_url="https://example.com/hook",
        client_factory=lambda: _TrackingClient(tracker),
    )
    result = await notifier.notify("message", level="success", title="Title", fields={"foo": "bar"})
    assert result is True
    assert tracker
    call = tracker[0]
    assert call["url"] == "https://example.com/hook"
    embed = call["payload"]["embeds"][0]
    assert embed["title"].startswith("✅")
    assert any(field["name"] == "foo" for field in embed.get("fields", []))
@pytest.mark.asyncio
async def test_notify_handles_http_errors() -> None:
    notifier = DiscordNotifier(
        webhook_url="https://example.com/hook",
        client_factory=lambda: _ErroringClient(),
    )
    result = await notifier.notify("message", level="error")
    assert result is False
def test_notify_blocking_runs_async_path() -> None:
    tracker: List[Dict[str, Any]] = []
    notifier = DiscordNotifier(
        webhook_url="https://example.com/hook",
        client_factory=lambda: _TrackingClient(tracker),
        run_sync=asyncio.run,
    )
    result = notifier.notify_blocking("blocking-call", level="debug")
    assert result is True
    assert tracker[0]["payload"]["embeds"][0]["title"].startswith("🔧")
