"""Tests for the VOICEVOX provider cooldown and fallback behaviour."""

from __future__ import annotations

from typing import Dict

import pytest
from requests import RequestException

from app.tts.providers import VoicevoxProvider


class DummyResponse:
    def __init__(self, status_code: int, json_data: Dict | None = None, content: bytes = b"") -> None:
        self.status_code = status_code
        self._json_data = json_data or {}
        self.content = content or b""

    def json(self) -> Dict:
        return self._json_data


@pytest.mark.asyncio
async def test_voicevox_provider_enters_cooldown(monkeypatch, tmp_path):
    clock = {"now": 100.0}
    calls = {"get": 0}

    provider = VoicevoxProvider(port=59999, health_cooldown_seconds=120)

    monkeypatch.setattr("app.tts.providers.time.monotonic", lambda: clock["now"])

    def failing_get(url, timeout):
        calls["get"] += 1
        raise RequestException("server down")

    monkeypatch.setattr("app.tts.providers.requests.get", failing_get)
    monkeypatch.setattr("app.tts.providers.requests.post", lambda *args, **kwargs: None)

    output_path = tmp_path / "voicevox.wav"

    result = await provider.synthesize("テスト音声", str(output_path))
    assert result is False
    assert calls["get"] == 1
    assert not output_path.exists()

    # 再試行してもクールダウン中はリクエストしない
    second_result = await provider.synthesize("テスト音声", str(output_path))
    assert second_result is False
    assert calls["get"] == 1

    # クールダウンを過ぎたら再度ヘルスチェックを試みる
    clock["now"] += 200

    def healthy_get(url, timeout):
        calls["get"] += 1
        return DummyResponse(status_code=200)

    def fake_post(url, params=None, json=None, timeout=None):  # noqa: A002 - mimic requests signature
        if "audio_query" in url:
            return DummyResponse(status_code=200, json_data={"query": "ok"})
        return DummyResponse(status_code=200, content=b"audio-bytes")

    monkeypatch.setattr("app.tts.providers.requests.get", healthy_get)
    monkeypatch.setattr("app.tts.providers.requests.post", fake_post)

    success_result = await provider.synthesize("テスト音声", str(output_path))
    assert success_result is True
    assert calls["get"] == 2
    assert output_path.exists()
