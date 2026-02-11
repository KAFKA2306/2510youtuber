"""Centralized LLM adapter for Gemini via LiteLLM."""
from __future__ import annotations
import importlib
import importlib.util
import inspect
import json
import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Type
import litellm
from crewai.llms.base_llm import BaseLLM
from pydantic import BaseModel
from app.api_rotation import get_rotation_manager
from app.config.settings import settings
from app.llm_logging import record_llm_interaction
_LOGGER = logging.getLogger(__name__)
_ALLOWED_GEN_ARGS = {
    "temperature",
    "top_p",
    "top_k",
    "max_output_tokens",
    "candidate_count",
    "stop_sequences",
    "safety_settings",
}
_CODE_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(.+?)```", re.IGNORECASE | re.DOTALL)
def _normalize_model(model: Optional[str]) -> str:
    candidate = model or settings.llm_model
    if not candidate:
        raise RuntimeError("Gemini model name is not configured")
    if "/" in candidate:
        return candidate
    return f"gemini/{candidate}"
def _merge_generation_config(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {k: v for k, v in base.items() if v is not None}
    for key, value in overrides.items():
        if key in _ALLOWED_GEN_ARGS and value is not None:
            merged[key] = value
    return merged
def _extract_message_text(response: Any) -> str:
    try:
        choices: Iterable[Any]
        if isinstance(response, dict):
            choices = response.get("choices", [])
        else:
            choices = getattr(response, "choices", [])
        if not isinstance(choices, list) or not choices:
            return str(response)
        first_choice = choices[0]
        if isinstance(first_choice, dict):
            message = first_choice.get("message") or first_choice.get("content") or first_choice.get("text")
        else:
            message = getattr(first_choice, "message", None) or getattr(first_choice, "text", None)
        if isinstance(message, dict):
            content = message.get("content") or message.get("text")
        else:
            content = message
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    parts.append(str(item["text"]))
                else:
                    parts.append(str(item))
            return "".join(parts).strip()
        if content is None:
            return ""
        return str(content).strip()
    except Exception as exc:
        _LOGGER.debug("Failed to parse LiteLLM response: %s", exc)
        return str(response)
def _find_json_bounds(text: str) -> Optional[str]:
    """Return the first balanced JSON object or array in *text*."""
    length = len(text)
    for index in range(length):
        start_char = text[index]
        if start_char not in "{[":
            continue
        stack: List[str] = ["}" if start_char == "{" else "]"]
        in_string = False
        escape = False
        for cursor in range(index + 1, length):
            char = text[cursor]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
                continue
            if char in "{[":
                stack.append("}" if char == "{" else "]")
                continue
            if char in "}]":
                if not stack:
                    break
                expected = stack.pop()
                if char != expected:
                    break
                if not stack:
                    return text[index : cursor + 1].strip()
    return None
def extract_structured_json(text: str) -> Optional[str]:
    """Extract a JSON object/array from LLM text output.
    Gemini responses sometimes wrap valid JSON with Markdown fences or
    explanatory prose. This helper strips common wrappers and returns the
    first balanced JSON payload when possible.
    """
    if not text:
        return None
    candidates: List[str] = []
    fence_match = _CODE_FENCE_PATTERN.search(text)
    if fence_match:
        candidates.append(fence_match.group(1))
    candidates.append(text)
    for candidate in candidates:
        snippet = _find_json_bounds(candidate.strip())
        if snippet:
            return snippet
    return None
def _resolve_original_completion() -> Optional[Any]:
    module_name = "app.crew.flows"
    if importlib.util.find_spec(module_name) is None:
        return None
    flows = importlib.import_module(module_name)
    return getattr(flows, "original_completion", None)
class CrewAIGeminiLLM(BaseLLM):
    """CrewAI-compatible LLM wrapper that delegates to :class:`LLMClient`."""
    def __init__(
        self,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        target_model = model or settings.llm_model
        base_init = super().__init__
        try:
            init_signature = inspect.signature(base_init)
        except (TypeError, ValueError):
            init_signature = None
        if init_signature is not None:
            parameters = init_signature.parameters
            accepts_var_kw = any(param.kind == inspect.Parameter.VAR_KEYWORD for param in parameters.values())
            base_dict = getattr(BaseLLM, "__dict__", {})
            declared_init = base_dict.get("__init__") if hasattr(base_dict, "get") else None
            has_named_params = any(
                name not in {"self", "args", "kwargs"}
                for name in parameters
            )
            if declared_init in (None, object.__init__) and not has_named_params:
                base_init()
            else:
                combined_kwargs: Dict[str, Any] = {
                    key: value for key, value in kwargs.items() if value is not None
                }
                combined_kwargs["model"] = target_model
                if temperature is not None:
                    combined_kwargs.setdefault("temperature", temperature)
                if stop is not None:
                    combined_kwargs.setdefault("stop", stop)
                init_kwargs: Dict[str, Any] = {}
                for name, param in parameters.items():
                    if name == "self":
                        continue
                    if name in combined_kwargs:
                        init_kwargs[name] = combined_kwargs[name]
                if accepts_var_kw:
                    for name, value in combined_kwargs.items():
                        if name not in init_kwargs:
                            init_kwargs[name] = value
                base_init(**init_kwargs)
        else:
            base_init()
        self.model = target_model
        self.temperature = temperature
        self.stop = stop
        generation_defaults: Dict[str, Any] = {
            key: value for key, value in kwargs.items() if key in _ALLOWED_GEN_ARGS and value is not None
        }
        if temperature is not None:
            generation_defaults.setdefault("temperature", temperature)
        passthrough: Dict[str, Any] = {
            key: kwargs[key] for key in ("api_key", "max_attempts") if key in kwargs and kwargs[key] is not None
        }
        passthrough.update(generation_defaults)
        self._client = LLMClient(model=target_model, **passthrough)
    def call(
        self,
        messages: Any,
        tools: Optional[List[Dict[str, Any]]] = None,
        callbacks: Optional[List[Any]] = None,
        available_functions: Optional[Dict[str, Any]] = None,
        from_task: Any = None,
        from_agent: Any = None,
    ) -> str:
        if tools:
            _LOGGER.debug("CrewAIGeminiLLM received tools but tool use is not supported yet")
        del callbacks, available_functions, from_task, from_agent
        if isinstance(messages, str):
            payload = [{"role": "user", "content": messages}]
        elif isinstance(messages, list):
            payload = messages
        else:
            raise TypeError("messages must be a string or a list of message dicts")
        generation_args: Dict[str, Any] = {}
        if self.stop:
            generation_args["stop_sequences"] = self.stop
        response = self._client.completion(messages=payload, **generation_args)
        text = _extract_message_text(response)
        try:
            record_llm_interaction(
                provider="gemini",
                model=self.model,
                prompt=payload,
                response={
                    "raw": response,
                    "text": text,
                },
                metadata={
                    "generation_args": generation_args or None,
                    "client": "CrewAIGeminiLLM",
                },
            )
        except Exception:
            _LOGGER.debug("Failed to record CrewAI Gemini interaction", exc_info=True)
        return text
    def supports_stop_words(self) -> bool:
        return True
    def supports_function_calling(self) -> bool:
        """CrewAI contract hook used for structured-output conversion."""
        return True
def get_crewai_gemini_llm(
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    stop: Optional[List[str]] = None,
    **kwargs: Any,
) -> CrewAIGeminiLLM:
    """Factory function used by CrewAI agent definitions."""
    return CrewAIGeminiLLM(model=model, temperature=temperature, stop=stop, **kwargs)
class LLMClient:
    """LiteLLM-backed Gemini client with rotation and config hygiene."""
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self.api_key = api_key or settings.gemini_api_key
        self.model = _normalize_model(model)
        self.max_attempts = int(kwargs.pop("max_attempts", 3))
        self.default_generation_config: Dict[str, Any] = {
            key: value for key, value in kwargs.items() if key in _ALLOWED_GEN_ARGS and value is not None
        }
        self._rotation_manager = get_rotation_manager()
    def completion(self, messages: List[Dict[str, Any]], **generation_args: Any) -> Any:
        cfg = _merge_generation_config(self.default_generation_config, generation_args)
        base_kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }
        if cfg:
            base_kwargs["extra_body"] = {"generationConfig": cfg}
        completion_fn = litellm.completion
        is_patched = getattr(completion_fn, "__name__", "") == "patched_completion"
        original_completion = _resolve_original_completion() if is_patched else None
        has_rotation_keys = bool(self._rotation_manager.key_pools.get("gemini"))
        def _call(target_fn: Any, api_key: Optional[str] = None) -> Any:
            request = dict(base_kwargs)
            if api_key:
                request["api_key"] = api_key
            return target_fn(**request)
        if self.api_key:
            target = original_completion or completion_fn
            _LOGGER.debug("LLMClient using explicit API key with model %s", base_kwargs["model"])
            return _call(target, api_key=self.api_key)
        if is_patched and has_rotation_keys:
            _LOGGER.debug("LLMClient delegating to patched LiteLLM for rotation")
            return _call(completion_fn)
        if has_rotation_keys:
            _LOGGER.debug("LLMClient invoking rotation manager directly")
            def _invoke(key: str) -> Any:
                return _call(completion_fn, api_key=key)
            return self._rotation_manager.execute_with_rotation(
                provider="gemini",
                api_call=_invoke,
                max_attempts=self.max_attempts,
            )
        fallback_key = settings.gemini_api_key
        if fallback_key:
            target = original_completion or completion_fn
            _LOGGER.debug("LLMClient using fallback API key for model %s", base_kwargs["model"])
            return _call(target, api_key=fallback_key)
        raise RuntimeError("Gemini API key is not configured")
    def generate(self, prompt: str, generation_config: Optional[Dict[str, Any]] = None) -> str:
        response = self.completion(
            messages=[{"role": "user", "content": prompt}],
            **(generation_config or {}),
        )
        return _extract_message_text(response)
    def generate_structured(
        self,
        prompt: str,
        schema: Optional[Type[BaseModel]] = None,
        generation_config: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Generate JSON-aligned output with light post-processing.
        Crew-side utilities often expect Gemini adapters to expose a
        ``generate_structured`` helper that attempts to coerce responses into
        dictionaries or Pydantic models. This method keeps that contract so the
        agent review cycle and other legacy callers remain functional.
        """
        raw = self.generate(prompt, generation_config=generation_config)
        if schema is not None:
            try:
                if isinstance(raw, BaseModel):
                    return raw
                if isinstance(raw, dict):
                    return schema.model_validate(raw)
                return schema.model_validate_json(str(raw))
            except Exception as exc:
                _LOGGER.debug("Schema validation failed in generate_structured: %s", exc)
        if isinstance(raw, BaseModel):
            return raw
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            cleaned = extract_structured_json(raw) or raw.strip()
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                _LOGGER.debug("Failed to JSON-decode structured output; returning raw text")
                return raw
        return raw
class AIClient:
    """Backward-compatible wrapper exposing the legacy generate() API."""
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, **kwargs: Any) -> None:
        self._client = LLMClient(api_key=api_key, model=model, **kwargs)
    def generate(self, prompt: str, generation_config: Optional[Dict[str, Any]] = None) -> str:
        return self._client.generate(prompt, generation_config)
class AIClientFactory:
    """Factory helper mirroring the historic interface."""
    @staticmethod
    def create(
        client_type: str,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        client_type = (client_type or "gemini").lower()
        if client_type == "gemini":
            return LLMClient(api_key=api_key, model=model, **kwargs)
        if client_type == "perplexity":
            from app.adapters.search import PerplexityClient
            if not api_key:
                raise ValueError("Perplexity client requires an API key")
            return PerplexityClient(api_key=api_key)
        raise ValueError(f"Unsupported client: {client_type}")
    get = create
    build = create
    from_env = create
class GeminiClient(LLMClient):
    """Alias maintained for legacy direct imports."""
    pass
__all__ = [
    "CrewAIGeminiLLM",
    "get_crewai_gemini_llm",
    "LLMClient",
    "GeminiClient",
    "AIClient",
    "AIClientFactory",
]
