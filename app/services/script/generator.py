"""Structured script generation service.

This module replaces the legacy multi-agent CrewAI flow with a single
Gemini-powered generation pass that returns a typed :class:`Script` model.
"""

from __future__ import annotations

import json
import logging
import textwrap
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError

from app.adapters.llm import LLMClient
from app.config.settings import settings
from app.services.script.validator import DialogueEntry, Script

logger = logging.getLogger(__name__)


class ScriptGenerationMetadata(BaseModel):
    """Optional quality metrics returned alongside the generated script."""

    wow_score: Optional[float] = Field(default=None, description="WOW score")
    japanese_purity_score: Optional[float] = Field(default=None, description="Japanese purity score (0-100)")
    retention_prediction: Optional[float] = Field(default=None, description="Predicted audience retention (0-1)")


class StructuredScriptPayload(BaseModel):
    """Schema expected from the LLM response."""

    title: str
    dialogues: List[DialogueEntry]
    summary: Optional[str] = None
    wow_score: Optional[float] = None
    japanese_purity_score: Optional[float] = None
    retention_prediction: Optional[float] = None

    def to_script(self) -> Script:
        # Pydantic will ignore the non-Script fields while validating
        return Script.model_validate(self.model_dump())

    def to_metadata(self) -> ScriptGenerationMetadata:
        return ScriptGenerationMetadata(
            wow_score=self.wow_score,
            japanese_purity_score=self.japanese_purity_score,
            retention_prediction=self.retention_prediction,
        )


@dataclass
class ScriptGenerationResult:
    """Typed container returned by the generator."""

    script: Script
    metadata: ScriptGenerationMetadata
    raw_response: str


class StructuredScriptGenerator:
    """Single-pass script generator backed by Gemini through :class:`LLMClient`."""

    def __init__(
        self,
        client: Optional[LLMClient] = None,
        max_attempts: int = 3,
        temperature: float = 0.6,
    ) -> None:
        self.max_attempts = max(1, max_attempts)
        model_name = settings.gemini_models.get("script_generation")
        self.client = client or LLMClient(model=model_name, temperature=temperature)
        self._allowed_speakers = [speaker.name for speaker in settings.speakers]

        if len(self._allowed_speakers) < 2:
            raise RuntimeError("At least two speakers must be configured for script generation")

    def generate(
        self,
        news_items: List[Dict[str, Any]],
        target_duration_minutes: Optional[int] = None,
    ) -> ScriptGenerationResult:
        """Generate a structured script for the provided news digest."""

        news_digest = self._format_news_digest(news_items)
        prompt = self._build_prompt(news_digest, target_duration_minutes)

        for attempt in range(1, self.max_attempts + 1):
            logger.info("Structured script generation attempt %s/%s", attempt, self.max_attempts)

            response = self.client.completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You craft finance YouTube dialogue scripts. Always return valid JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ]
            )

            response_text = self._extract_message_text(response)
            logger.debug("LLM raw response (first 400 chars): %r", response_text[:400])

            try:
                payload = self._parse_payload(response_text)
            except ValueError as exc:
                logger.warning("Structured script parse failed: %s", exc)
                continue

            script = payload.to_script()
            metadata = payload.to_metadata()

            return ScriptGenerationResult(script=script, metadata=metadata, raw_response=response_text)

        raise RuntimeError("Structured script generation failed after all attempts")

    def _build_prompt(self, news_digest: str, target_duration_minutes: Optional[int]) -> str:
        speaker_list = ", ".join(self._allowed_speakers)

        duration_hint = (
            f"目標尺はおよそ{target_duration_minutes}分です。" if target_duration_minutes else ""
        )

        template = f"""
        以下の金融ニュース要約に基づき、視聴者が理解しやすい対話形式の台本を作成してください。

        {duration_hint}

        出力条件:
        - 話者は必ず以下の名前のみを使用: {speaker_list}
        - 各台詞は「{{speaker}}: {{line}}」形式にできる内容で、日本語で書く
        - 行頭に話者名を付与し、会話を最低24ターン以上構成する
        - 数値・視覚指示・行動提案を織り交ぜる
        - JSON形式のみで回答し、余計な文章やコードブロックは付けない

        出力JSONのスキーマ例:
        {{
          "title": "string",
          "summary": "string",
          "dialogues": [
            {{ "speaker": "{self._allowed_speakers[0]}", "line": "対話文" }}
          ],
          "wow_score": 8.2,
          "japanese_purity_score": 97.5,
          "retention_prediction": 0.54
        }}

        ニュース要約:
        {news_digest}
        """

        return textwrap.dedent(template).strip()

    @staticmethod
    def _extract_message_text(response: Any) -> str:
        """Mirror logic from :func:`app.adapters.llm._extract_message_text`."""

        if isinstance(response, dict) and "choices" in response:
            try:
                choice = response["choices"][0]
                message = choice.get("message") or choice.get("content")
                if isinstance(message, dict):
                    return str(message.get("content") or message.get("text") or "").strip()
                if isinstance(message, list):
                    return "".join(str(part.get("text", part)) for part in message).strip()
                if message is not None:
                    return str(message).strip()
            except Exception:  # pragma: no cover - defensive path
                pass
        return str(response).strip()

    def _parse_payload(self, response_text: str) -> StructuredScriptPayload:
        json_blob = self._extract_json_block(response_text)
        if not json_blob:
            raise ValueError("No JSON object found in LLM response")

        try:
            data = json.loads(json_blob)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed JSON: {exc}") from exc

        try:
            return StructuredScriptPayload.model_validate(data)
        except ValidationError as exc:
            raise ValueError(f"Structured payload validation failed: {exc}") from exc

    @staticmethod
    def _extract_json_block(text: str) -> Optional[str]:
        stripped = text.strip()
        if not stripped:
            return None

        if stripped.startswith("{"):
            if StructuredScriptGenerator._is_balanced_json(stripped):
                return stripped

        start = stripped.find("{")
        if start == -1:
            return None

        slice_text = stripped[start:]
        end_index = StructuredScriptGenerator._find_matching_brace(slice_text)
        if end_index is None:
            return None
        candidate = slice_text[: end_index + 1]
        return candidate if StructuredScriptGenerator._is_balanced_json(candidate) else None

    @staticmethod
    def _find_matching_brace(text: str) -> Optional[int]:
        depth = 0
        for idx, char in enumerate(text):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return idx
        return None

    @staticmethod
    def _is_balanced_json(text: str) -> bool:
        try:
            json.loads(text)
            return True
        except json.JSONDecodeError:
            return False

    @staticmethod
    def _format_news_digest(news_items: List[Dict[str, Any]]) -> str:
        if not news_items:
            return "(ニュース項目が提供されていません)"

        lines: List[str] = []
        for index, item in enumerate(news_items, start=1):
            title = item.get("title") or item.get("headline") or f"ニュース{index}"
            summary = item.get("summary") or item.get("description") or "概要不明"
            source = item.get("source") or "不明"
            impact = item.get("impact_level") or item.get("importance") or "medium"

            lines.append(
                textwrap.dedent(
                    f"""
                    ■ {index}. {title}
                       出典: {source} / 重要度: {impact}
                       要約: {summary}
                    """
                ).strip()
            )

        return "\n\n".join(lines)

