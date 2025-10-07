"""Failure bus primitives for the asynchronous workflow pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - circular import guard for type checking only
    from .base import WorkflowContext


@dataclass
class WorkflowFailureEvent:
    """Payload describing a workflow failure notification."""

    step_name: str
    context: Optional["WorkflowContext"]
    result: Optional[Any] = None
    error: Optional[BaseException] = None
    response: Optional[Any] = None


FailureSubscriber = Callable[["WorkflowFailureEvent"], Awaitable[None]]


class FailureBus:
    """Simple async pub/sub bus for workflow failure events."""

    def __init__(self) -> None:
        self._subscribers: List[FailureSubscriber] = []

    def subscribe(self, subscriber: FailureSubscriber) -> None:
        """Register a subscriber that will be awaited when a failure occurs."""

        self._subscribers.append(subscriber)

    async def notify(self, event: WorkflowFailureEvent) -> WorkflowFailureEvent:
        """Notify all subscribers sequentially and return the enriched event."""

        for subscriber in self._subscribers:
            await subscriber(event)
        return event
