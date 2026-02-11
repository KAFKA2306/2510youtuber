"""Centralized workflow prompt helpers."""
from __future__ import annotations
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, Optional
from app.config_prompts.settings import settings
_PROMPT_DEFAULTS_TEMPLATE_NAME = "prompt_defaults"
@lru_cache(maxsize=1)
def _load_prompt_defaults() -> Dict[str, Any]:
    """Return the structured prompt defaults loaded from the prompt manager."""
    data = settings.prompt_manager.load_structured_template(_PROMPT_DEFAULTS_TEMPLATE_NAME)
    return data or {}
def _workflow_defaults() -> Dict[str, Any]:
    return _load_prompt_defaults().get("workflow", {})
def _news_collection_defaults() -> Dict[str, Any]:
    return _workflow_defaults().get("news_collection", {})
def get_default_news_collection_prompt() -> str:
    """Return the default base prompt for news collection (prompt A)."""
    base_prompt: str = _news_collection_defaults().get("base_prompt", "")
    return base_prompt.strip()
def get_news_collection_system_message() -> str:
    """Return the system message used for the news collection LLM."""
    message: str = _news_collection_defaults().get("system_message", "")
    return message.strip()
def get_default_script_generation_prompt() -> str:
    """Return the default base prompt for script generation (prompt B)."""
    script_defaults: Dict[str, Any] = _workflow_defaults().get("script_generation", {})
    base_prompt: str = script_defaults.get("base_prompt", "")
    return base_prompt.strip()
def _render_template_text(template_text: str, context: Dict[str, Any]) -> str:
    if not template_text:
        return ""
    rendered = settings.prompt_manager.render_text(template_text, context)
    return rendered.strip()
def build_news_collection_prompt(
    base_prompt: Optional[str],
    mode: str,
    *,
    current_date: Optional[datetime] = None,
) -> str:
    """Construct the final news collection prompt for the given *mode*."""
    prompt_text = (base_prompt or "").strip() or get_default_news_collection_prompt()
    defaults = _news_collection_defaults()
    adjustments: Dict[str, str] = defaults.get("adjustments", {})
    context = {
        "current_date": (current_date or datetime.now()).strftime("%Y年%m月%d日"),
    }
    adjustment = _render_template_text(adjustments.get(mode, ""), context)
    response_format = _render_template_text(defaults.get("response_format", ""), context)
    parts = [prompt_text]
    if adjustment:
        parts.append(adjustment)
    if response_format:
        parts.append(response_format)
    return "\n\n".join(part for part in parts if part)
def get_sheet_prompt_defaults() -> Dict[str, str]:
    """Return the default prompt set used when Sheets configuration is missing."""
    sheet_defaults: Dict[str, Any] = _load_prompt_defaults().get("sheets_defaults", {})
    return {key: (value.strip() if isinstance(value, str) else value) for key, value in sheet_defaults.items()}
