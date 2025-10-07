"""Structured logging utilities for LLM prompt/response tracking."""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, Optional

import yaml

from app.config.paths import ProjectPaths
from app.logging_config import get_log_session

_LOGGER = logging.getLogger(__name__)


def _make_serializable(value: Any) -> Any:
    """Convert *value* into YAML-serializable data."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): _make_serializable(subvalue) for key, subvalue in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_make_serializable(item) for item in value]
    if hasattr(value, "model_dump"):
        try:
            return _make_serializable(value.model_dump())
        except Exception:  # pragma: no cover - best effort
            return str(value)
    if hasattr(value, "dict"):
        try:
            return _make_serializable(value.dict())
        except Exception:  # pragma: no cover - best effort
            return str(value)
    return str(value)


def _current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class _ContextStore:
    """Thread-local LLM logging context."""

    def __init__(self) -> None:
        self._local = threading.local()

    def get(self) -> Dict[str, Any]:
        base: Dict[str, Any] = getattr(self._local, "value", {})
        return dict(base)

    def set(self, value: Dict[str, Any]) -> None:
        self._local.value = dict(value)

    def update(self, **kwargs: Any) -> None:
        current = self.get()
        current.update({k: v for k, v in kwargs.items() if v is not None})
        self.set(current)

    @contextmanager
    def push(self, **kwargs: Any) -> Generator[None, None, None]:
        previous = self.get()
        self.update(**kwargs)
        try:
            yield
        finally:
            self.set(previous)


_CONTEXT = _ContextStore()


class LLMInteractionLogger:
    """Persist structured records of LLM prompts and responses."""

    def __init__(self, log_path: Optional[Path] = None) -> None:
        self.log_path = (log_path or ProjectPaths.logs_path("llm_interactions.yaml")).resolve()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()

    def log_interaction(
        self,
        *,
        provider: str,
        model: Optional[str],
        prompt: Any,
        response: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append a YAML document with prompt, response, and context information."""

        session = get_log_session()
        context = _CONTEXT.get()
        payload: Dict[str, Any] = {
            "timestamp": _current_timestamp(),
            "provider": provider,
            "model": model,
            "prompt": _make_serializable(prompt),
            "response": _make_serializable(response),
            "context": context or None,
            "metadata": _make_serializable(metadata) if metadata else None,
        }

        if session is not None:
            payload["session_id"] = session.session_id
            payload["run_id"] = getattr(session._filter, "run_id", None) if getattr(session, "_filter", None) else None

        payload = {key: value for key, value in payload.items() if value is not None}

        document = yaml.safe_dump(
            payload,
            allow_unicode=True,
            sort_keys=False,
        )
        if not document.endswith("\n"):
            document += "\n"
        entry = f"---\n{document}"

        try:
            with self._write_lock:
                with self.log_path.open("a", encoding="utf-8") as handle:
                    handle.write(entry)
        except Exception as exc:  # pragma: no cover - logging must be fire-and-forget
            _LOGGER.debug("Failed to write LLM interaction log: %s", exc)


_LOGGER_INSTANCE: Optional[LLMInteractionLogger] = None
_LOGGER_LOCK = threading.Lock()


def get_llm_logger() -> LLMInteractionLogger:
    global _LOGGER_INSTANCE
    if _LOGGER_INSTANCE is None:
        with _LOGGER_LOCK:
            if _LOGGER_INSTANCE is None:
                _LOGGER_INSTANCE = LLMInteractionLogger()
    return _LOGGER_INSTANCE


@contextmanager
def llm_logging_context(**kwargs: Any) -> Generator[None, None, None]:
    """Temporarily enrich interaction logs with contextual metadata."""

    with _CONTEXT.push(**kwargs):
        yield


def record_llm_interaction(
    *,
    provider: str,
    model: Optional[str],
    prompt: Any,
    response: Any,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Convenience wrapper that records an interaction using the singleton logger."""

    logger = get_llm_logger()
    logger.log_interaction(provider=provider, model=model, prompt=prompt, response=response, metadata=metadata)
