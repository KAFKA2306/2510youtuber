"""Legacy script generation helpers with lightweight dependency injection."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Mapping
from typing import Any, Optional

import yaml

from app.crew.flows import create_wow_script_crew
from app.crew.tools.ai_clients import GeminiClient
from app.services.script.validator import Script

logger = logging.getLogger(__name__)


def _extract_script_from_llm_output(llm_output: str) -> str:
    """Extracts the script from the LLM output, which may contain extra text."""
    # It could be a YAML mapping
    try:
        data = yaml.safe_load(llm_output)
        if isinstance(data, Mapping) and "dialogues" in data and "title" in data:
            return Script.model_validate(data).to_text()
    except yaml.YAMLError:
        pass

    # It could be a script with leading/trailing text
    lines = llm_output.split('\n')
    script_lines = []
    in_script = False
    for line in lines:
        if re.match(r"^(田中|鈴木|ナレーター|司会)[:：]", line):
            in_script = True
        if in_script:
            script_lines.append(line)

    if script_lines:
        return "\n".join(script_lines)

    return llm_output # Return original if we can't find anything


class ScriptGenerator:
    """Facilitates Gemini-powered script creation with optional CrewAI support."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-1.5-flash",
        *,
        client: Callable[[str, dict[str, Any] | None], str] | Any | None = None,
        crew_runner: Callable[..., Script | Mapping[str, Any]] | None = None,
    ) -> None:
        if client is None and api_key:
            client = GeminiClient(api_key=api_key, model=model)
        if client is not None and hasattr(client, "generate"):
            client = client.generate
        self._generate: Optional[Callable[[str, dict[str, Any] | None], str]] = client  # type: ignore[assignment]
        self._crew_runner: Callable[..., Script | Mapping[str, Any]] = crew_runner or create_wow_script_crew

    def generate_with_crewai(self, news_items: list, *, target_duration_minutes: int | None = None) -> Script:
        return self.generate_crewai_payload(
            news_items,
            target_duration_minutes=target_duration_minutes,
        )["script_model"]

    def generate_crewai_payload(
        self,
        news_items: list,
        *,
        target_duration_minutes: int | None = None,
    ) -> dict[str, Any]:
        payload = self._run(
            "CrewAI script generation",
            lambda: self._crew_runner(news_items=news_items, target_duration_minutes=target_duration_minutes),
        )
        payload_mapping: Mapping[str, Any] = payload if isinstance(payload, Mapping) else {}
        if payload_mapping.get("success") is False:
            raise RuntimeError(payload_mapping.get("error") or "CrewAI execution failed")
        script = self.ensure_script(payload)
        structured_yaml = payload_mapping.get("structured_script_yaml") if payload_mapping else None
        structured_payload, structured_yaml = self.ensure_structured_payload(script, structured_yaml)
        return {
            "script": script.to_text(),
            "script_model": script,
            "crew_result": payload,
            "structured_script": structured_payload,
            "structured_script_yaml": structured_yaml,
        }

    def _run(self, label: str, operation: Callable[[], Any]) -> Any:
        try:
            return operation()
        except Exception as exc:  # pragma: no cover - just logging
            logger.error("%s failed: %s", label, exc)
            raise

    @staticmethod
    def ensure_script(payload: Script | Mapping[str, Any]) -> Script:
        if isinstance(payload, Script):
            return payload
        if not isinstance(payload, Mapping):
            raise TypeError(f"Unsupported CrewAI payload type: {type(payload)}")

        candidate = payload.get("final_script") or payload.get("script")
        if isinstance(candidate, Script):
            return candidate
        if isinstance(candidate, Mapping):
            return Script.model_validate(candidate)

        raise TypeError("CrewAI result did not contain a Script payload")

    @staticmethod
    def ensure_structured_payload(script: Script, yaml_blob: str | None) -> tuple[dict[str, Any], str]:
        if isinstance(yaml_blob, str):
            try:
                payload = yaml.safe_load(yaml_blob) or {}
            except yaml.YAMLError as exc:  # pragma: no cover - best effort logging
                logger.warning("Failed to parse structured script YAML: %s", exc)
            else:
                return payload, yaml_blob

        payload = script.model_dump(mode="json")
        fallback_yaml = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
        return payload, fallback_yaml


def generate_dialogue(
    news_items: list[dict[str, Any]],
    prompt: str,
    *,
    target_duration_minutes: int | None = None,
    use_quality_check: bool = True,
) -> str:
    """Generate a dialogue script using the configured quality pipeline."""

    if use_quality_check:
        from app.script_quality import generate_high_quality_script

        result = generate_high_quality_script(
            news_items,
            prompt,
            target_duration_minutes or 30,
        )
        if result.get("success") and result.get("final_script"):
            final_script = result["final_script"]
            if isinstance(final_script, Script):
                return final_script.to_text()
            if isinstance(final_script, Mapping):
                return Script.model_validate(final_script).to_text()
            if isinstance(final_script, str):
                return _extract_script_from_llm_output(final_script)
        raise RuntimeError(result.get("error") or "Three-stage script generation failed")

    from app.services.script.generator import StructuredScriptGenerator

    structured = StructuredScriptGenerator().generate(
        news_items,
        target_duration_minutes,
    )
    return structured.script.to_text()
