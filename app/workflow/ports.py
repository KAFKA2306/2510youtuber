"""Workflow port definitions for asynchronous orchestration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, Dict, List, Protocol


class NewsCollectionPort(Protocol):
    """Abstract port for collecting news items asynchronously."""

    async def collect_news(self, prompt: str, mode: str) -> List[Dict[str, Any]]:
        """Collect news articles for the given prompt and workflow mode."""


class SyncNewsCollectionAdapter:
    """Adapter that offloads synchronous news collection to a worker thread."""

    def __init__(self, collector: Callable[[str, str], List[Dict[str, Any]]]):
        self._collector = collector

    async def collect_news(self, prompt: str, mode: str) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._collector, prompt, mode)
