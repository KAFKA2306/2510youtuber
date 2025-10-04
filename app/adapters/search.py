"""Search service adapters (e.g., Perplexity)."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class PerplexityClient:
    """Perplexity API client wrapper."""

    def __init__(self, api_key: str, base_url: str = "https://api.perplexity.ai/chat/completions") -> None:
        self.api_key = api_key
        self.base_url = base_url

    def search(self, query: str, model: str = "sonar-medium-online", timeout: Optional[float] = 30) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": query}],
        }
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(self.base_url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except Exception as exc:  # pragma: no cover - network failure path
            logger.error("Perplexity search error: %s", exc)
            raise


__all__ = ["PerplexityClient"]
