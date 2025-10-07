"""Notification interfaces for workflow integrations."""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class Notifier(Protocol):
    """Asynchronous interface for workflow notifications."""

    async def notify(
        self,
        message: str,
        *,
        level: str = "info",
        title: Optional[str] = None,
        fields: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send a notification with optional metadata."""

