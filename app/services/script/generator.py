"""Structured script generation service.

This module replaces the legacy multi-agent CrewAI flow with a single
Gemini-powered generation pass that returns a typed :class:`Script` model.
"""

from __future__ import annotations

import json
import logging
import textwrap
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError

from app.adapters.llm import LLMClient
from app.adapters.llm import _extract_message_text as adapter_extract_message_text
from app.config.settings import settings
from app.services.script.validator import (
    DialogueEntry,
    Script,
    ScriptFormatError,
    ScriptValidationResult,
    ensure_dialogue_structure,
)

logger = logging.getLogger(__name__)


class ScriptGenerationMetadata(BaseModel):
    """Optional quality metrics returned alongside the generated script."""

    wow_score: Optional[float] = Field(default=None, description="WOW score")
    japanese_purity_score: Optional[float] = Field(
        default=None, description="Japanese purity score (0-100)"
    )
    retention_prediction: Optional[float] = Field(
        default=None, description="Predicted audience retention (0-1)"
    )
    quality_report: Optional["ScriptQualityReport"] = Field(
        default=None, description="Static quality heuristics calculated locally"
    )


class ScriptQualityReport(BaseModel):
    """Static dialogue quality heuristics independent from the LLM."""

    dialogue_lines: int
    total_nonempty_lines: int
    distinct_speakers: int
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


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
        self._quality_gate_enabled = settings.script_generation.quality_gate_llm_enabled

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

        fallback_candidate: Optional[ScriptGenerationResult] = None
        last_error: Optional[str] = None

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
                last_error = str(exc)
                try:
                    script, quality_report = self._build_script_from_text(response_text)
                except ValueError as fallback_error:
                    logger.warning("Fallback script conversion failed: %s", fallback_error)
                    last_error = str(fallback_error)
                    continue

                metadata = ScriptGenerationMetadata(quality_report=quality_report)
                fallback_candidate = ScriptGenerationResult(
                    script=script,
                    metadata=metadata,
                    raw_response=response_text,
                )
                if not self._quality_gate_enabled:
                    return fallback_candidate
                logger.info("Quality gate enabled; retrying after fallback candidate")
                continue

            script = payload.to_script()
            metadata = payload.to_metadata()
            metadata.quality_report = self._compute_quality_report(script)

            return ScriptGenerationResult(script=script, metadata=metadata, raw_response=response_text)

        if fallback_candidate:
            logger.warning("Returning fallback script after all attempts failed to parse JSON")
            return fallback_candidate

        logger.error(
            "Structured script generation exhausted all attempts: %s", last_error or "unknown error"
        )

        backup_script = self._build_backup_script(news_items, target_duration_minutes)
        backup_report = self._compute_quality_report(backup_script)
        metadata = ScriptGenerationMetadata(quality_report=backup_report)

        return ScriptGenerationResult(
            script=backup_script,
            metadata=metadata,
            raw_response="",
        )

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
    def _extract_message_text(response: Dict[str, Any]) -> str:
        """Expose adapter helper for tests and fallback paths."""

        return adapter_extract_message_text(response)

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

    def _build_script_from_text(self, response_text: str) -> Tuple[Script, ScriptQualityReport]:
        """Derive a :class:`Script` from arbitrary LLM output."""

        validation: Optional[ScriptValidationResult] = None
        try:
            validation = ensure_dialogue_structure(
                response_text,
                allowed_speakers=self._allowed_speakers,
                min_dialogue_lines=10,
            )
        except ScriptFormatError as exc:
            validation = exc.result
            logger.debug("Dialogue structure issues: %s", exc)

        dialogues = self._dialogues_from_validation(validation)

        if not dialogues:
            dialogues = self._fabricate_dialogues(response_text)

        title = self._infer_title(response_text)
        script = Script(title=title, dialogues=dialogues)
        quality_report = self._build_quality_report_from_validation(validation, script)

        return script, quality_report

    def _dialogues_from_validation(
        self, validation: Optional[ScriptValidationResult]
    ) -> List[DialogueEntry]:
        if not validation:
            return []

        dialogues: List[DialogueEntry] = []
        for raw_line in validation.normalized_script.splitlines():
            stripped = raw_line.strip()
            if not stripped or ":" not in stripped:
                continue
            speaker, content = stripped.split(":", 1)
            speaker = speaker.strip()
            content = content.strip() or "(内容未設定)"
            dialogues.append(DialogueEntry(speaker=speaker, line=content))

        return dialogues

    def _fabricate_dialogues(self, response_text: str) -> List[DialogueEntry]:
        dialogues: List[DialogueEntry] = []

        for raw_line in response_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            speaker = None
            content = line

            if ":" in line:
                potential, remainder = line.split(":", 1)
                normalized_speaker = potential.strip()
                remainder = remainder.strip()
                if remainder:
                    speaker = normalized_speaker
                    content = remainder

            if speaker is None:
                speaker = self._allowed_speakers[len(dialogues) % len(self._allowed_speakers)]
            if not content:
                content = "(内容未設定)"

            dialogues.append(DialogueEntry(speaker=speaker, line=content))

        if not dialogues:
            raise ValueError("No dialogue lines discovered in text output")

        if len(dialogues) == 1:
            alternate = self._allowed_speakers[1 % len(self._allowed_speakers)]
            dialogues.append(DialogueEntry(speaker=alternate, line="(補完台詞)"))

        return dialogues

    def _infer_title(self, response_text: str) -> str:
        for line in response_text.splitlines():
            candidate = line.strip()
            if not candidate:
                continue
            if candidate.startswith("{"):
                continue
            return candidate[:80]
        return "自動生成スクリプト"

    def _build_quality_report_from_validation(
        self,
        validation: Optional[ScriptValidationResult],
        script: Script,
    ) -> ScriptQualityReport:
        if not validation:
            return ScriptQualityReport(
                dialogue_lines=len(script.dialogues),
                total_nonempty_lines=len(script.dialogues),
                distinct_speakers=len({d.speaker for d in script.dialogues}),
                warnings=[],
                errors=[],
            )

        return ScriptQualityReport(
            dialogue_lines=validation.dialogue_line_count,
            total_nonempty_lines=validation.nonempty_line_count,
            distinct_speakers=sum(1 for count in validation.speaker_counts.values() if count > 0),
            warnings=[issue.message for issue in validation.warnings],
            errors=[issue.message for issue in validation.errors],
        )

    def _compute_quality_report(self, script: Script) -> ScriptQualityReport:
        try:
            validation = ensure_dialogue_structure(
                script.to_text(),
                allowed_speakers=self._allowed_speakers,
                min_dialogue_lines=10,
            )
        except ScriptFormatError as exc:
            validation = exc.result

        return self._build_quality_report_from_validation(validation, script)

    def _build_backup_script(
        self,
        news_items: List[Dict[str, Any]],
        target_duration_minutes: Optional[int] = None,
    ) -> Script:
        """Return a deterministic emergency script when the LLM fully fails."""

        topics: List[Dict[str, str]] = []
        for index, item in enumerate(news_items, start=1):
            topics.append(
                {
                    "title": str(item.get("title") or item.get("headline") or f"トピック{index}"),
                    "summary": str(
                        item.get("summary")
                        or item.get("description")
                        or "市場動向の詳細は追加調査が必要です。"
                    ),
                    "impact": str(item.get("impact_level") or item.get("importance") or "medium"),
                    "source": str(item.get("source") or "情報源不明"),
                }
            )

        if not topics:
            topics = [
                {
                    "title": "マーケット最新動向",
                    "summary": "主要指標とリスクイベントを振り返りながら今後の注意点を共有します。",
                    "impact": "medium",
                    "source": "社内調査",
                }
            ]

        primary = self._allowed_speakers[0]
        secondary = self._allowed_speakers[1]
        narrator = self._allowed_speakers[2] if len(self._allowed_speakers) > 2 else None

        dialogues: List[DialogueEntry] = []

        def add_dialogue(speaker: str, line: str) -> None:
            dialogues.append(DialogueEntry(speaker=speaker, line=line))

        duration_hint = (
            f"尺はおよそ{target_duration_minutes}分を想定しています。"
            if target_duration_minutes
            else ""
        )

        add_dialogue(primary, "こんばんは、今日もマーケットの振り返りを始めましょう。")
        add_dialogue(secondary, "よろしくお願いします。最初の注目トピックから教えてください。")
        if narrator:
            add_dialogue(narrator, duration_hint or "番組の流れを整理しながら解説します。")

        for idx, topic in enumerate(topics, start=1):
            add_dialogue(
                primary,
                f"{idx}つ目は『{topic['title']}』です。重要度は{topic['impact']}、情報源は{topic['source']}です。",
            )
            add_dialogue(
                secondary,
                f"要点をまとめると、{topic['summary']}",
            )
            add_dialogue(
                primary,
                "投資家として意識したいリスクとチャンスを整理していきましょう。",
            )
            if narrator:
                add_dialogue(
                    narrator,
                    "視聴者の皆さんはご自身のポートフォリオでの影響度をチェックしてみてください。",
                )
            add_dialogue(
                secondary,
                "短期的な値動きだけでなく、中長期の構造変化にも目を向けたいですね。",
            )
            add_dialogue(
                primary,
                "データポイントや企業コメントが更新されたら、概要欄のリンクでフォローしてください。",
            )

        add_dialogue(
            secondary,
            "他にも気になる指標があればコメントで教えてください。追加解説を検討します。",
        )
        add_dialogue(
            primary,
            "最後に具体的なアクションプランを3つまとめます。",
        )
        add_dialogue(primary, "① ポジションサイズの見直し、② リスクイベント前のヘッジ、③ 指標速報のウォッチです。")
        if narrator:
            add_dialogue(
                narrator,
                "概要欄には参考リンクと免責事項を記載しています。投資判断はご自身でお願いします。",
            )
        add_dialogue(
            secondary,
            "引き続き最新のマーケット情報をお届けしますので、チャンネル登録もお忘れなく。",
        )
        add_dialogue(primary, "ご視聴ありがとうございました。それではまた次回お会いしましょう。")

        while len(dialogues) < 24:
            speaker = self._allowed_speakers[len(dialogues) % len(self._allowed_speakers)]
            add_dialogue(speaker, "補足情報を追記し、マーケットの変化に備えましょう。")

        title_prefix = "バックアップ台本"
        headline = topics[0]["title"]
        title = f"{title_prefix}: {headline}"[:80]

        return Script(title=title, dialogues=dialogues)

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


ScriptGenerationMetadata.model_rebuild()

