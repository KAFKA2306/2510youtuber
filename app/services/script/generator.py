from __future__ import annotations

import logging
import re
import textwrap
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import yaml
from pydantic import BaseModel, Field, ValidationError

from app.adapters.llm import LLMClient
from app.adapters.llm import _extract_message_text as adapter_extract_message_text
from app.config.settings import settings
from app.services.script.speakers import get_speaker_registry
from app.services.script.validator import (
    DialogueEntry,
    Script,
    ScriptFormatError,
    ScriptValidationResult,
    ensure_dialogue_structure,
)

logger = logging.getLogger(__name__)

class ScriptGenerationMetadata(BaseModel):
    wow_score: Optional[float] = Field(default=None, description='WOW score')
    japanese_purity_score: Optional[float] = Field(default=None, description='Japanese purity score (0-100)')
    retention_prediction: Optional[float] = Field(default=None, description='Predicted audience retention (0-1)')
    quality_report: Optional['ScriptQualityReport'] = Field(default=None, description='Static quality heuristics calculated locally')

class ScriptQualityReport(BaseModel):
    dialogue_lines: int
    total_nonempty_lines: int
    distinct_speakers: int
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)

class StructuredScriptPayload(BaseModel):
    title: str
    dialogues: List[DialogueEntry]
    summary: Optional[str] = None
    wow_score: Optional[float] = None
    japanese_purity_score: Optional[float] = None
    retention_prediction: Optional[float] = None

    def to_script(self) -> Script:
        return Script.model_validate(self.model_dump())

    def to_metadata(self) -> ScriptGenerationMetadata:
        return ScriptGenerationMetadata(wow_score=self.wow_score, japanese_purity_score=self.japanese_purity_score, retention_prediction=self.retention_prediction)

@dataclass
class ScriptGenerationResult:
    script: Script
    metadata: ScriptGenerationMetadata
    raw_response: str
    structured_yaml: str

class SpeakerRoster:
    MIN_SPEAKERS = 2
    DEFAULT_PLACEHOLDERS = ('ナビゲーター', 'アナリスト')

    def __init__(self, speakers: Iterable[str]) -> None:
        cleaned = [name.strip() for name in speakers if isinstance(name, str) and name.strip()]
        self.configured_names: List[str] = list(cleaned)
        self.added_names: List[str] = []
        while len(cleaned) < self.MIN_SPEAKERS:
            next_name = self._next_placeholder(cleaned)
            cleaned.append(next_name)
            self.added_names.append(next_name)
        self._names = cleaned

    @classmethod
    def from_settings(cls) -> 'SpeakerRoster':
        return cls((speaker.name for speaker in settings.speakers))

    @staticmethod
    def _next_placeholder(current: List[str]) -> str:
        for candidate in SpeakerRoster.DEFAULT_PLACEHOLDERS:
            if candidate not in current:
                return candidate
        index = 1
        while True:
            candidate = f'話者{index}'
            if candidate not in current:
                return candidate
            index += 1

    @property
    def names(self) -> List[str]:
        return list(self._names)

    @property
    def was_augmented(self) -> bool:
        return bool(self.added_names)

    @property
    def warning_message(self) -> Optional[str]:
        if not self.was_augmented:
            return None
        joined = '、'.join(self.added_names)
        return f'設定された話者が不足していたため、台本生成で代替話者({joined})を補っています。'

class StructuredScriptGenerator:

    def __init__(self, client: Optional[LLMClient]=None, max_attempts: int=3, temperature: float=0.6, allowed_speakers: Optional[Sequence[str]]=None) -> None:
        self.max_attempts = max(1, max_attempts)
        model_name = settings.gemini_models.get('script_generation')
        self.client = client or LLMClient(model=model_name, temperature=temperature)
        self._speaker_roster = SpeakerRoster(allowed_speakers) if allowed_speakers is not None else SpeakerRoster.from_settings()
        self._allowed_speakers = self._speaker_roster.names
        self._allowed_speaker_set = {name for name in self._allowed_speakers if name}
        self._alias_lookup = get_speaker_registry().alias_map
        self._quality_gate_enabled = settings.script_generation.quality_gate_llm_enabled
        if self._speaker_roster.was_augmented:
            logger.warning('Speaker roster augmented with fallback names: configured=%s, added=%s', self._speaker_roster.configured_names, self._speaker_roster.added_names)

    def generate(self, news_items: List[Dict[str, Any]], target_duration_minutes: Optional[int]=None) -> ScriptGenerationResult:
        news_digest = self._format_news_digest(news_items)
        prompt = self._build_prompt(news_digest, target_duration_minutes)
        fallback_candidate: Optional[ScriptGenerationResult] = None
        last_error: Optional[str] = None
        for attempt in range(1, self.max_attempts + 1):
            logger.info('Structured script generation attempt %s/%s', attempt, self.max_attempts)
            response = self.client.completion(messages=[{'role': 'system', 'content': 'You craft finance YouTube dialogue scripts. Always return a valid YAML mapping only.'}, {'role': 'user', 'content': prompt}])
            response_text = self._extract_message_text(response)
            logger.debug('LLM raw response (first 400 chars): %r', response_text[:400])
            try:
                payload = self._parse_payload(response_text)
            except ValueError as exc:
                logger.warning('Structured script parse failed: %s', exc)
                last_error = str(exc)
                try:
                    script, quality_report = self._build_script_from_text(response_text)
                except ValueError as fallback_error:
                    logger.warning('Fallback script conversion failed: %s', fallback_error)
                    last_error = str(fallback_error)
                    continue
                try:
                    structured_yaml = self._dump_script_to_yaml(script)
                except ValueError as yaml_error:
                    logger.warning('Failed to serialize fallback script to YAML: %s', yaml_error)
                    last_error = str(yaml_error)
                    continue
                metadata = ScriptGenerationMetadata(quality_report=quality_report)
                fallback_candidate = ScriptGenerationResult(
                    script=script,
                    metadata=metadata,
                    raw_response=response_text,
                    structured_yaml=structured_yaml,
                )
                if not self._quality_gate_enabled:
                    return fallback_candidate
                logger.info('Quality gate enabled; retrying after fallback candidate')
                continue
            try:
                script = payload.to_script()
            except ValidationError as exc:
                logger.warning('Structured payload failed validation: %s', exc)
                try:
                    repaired_dialogues = self._ensure_min_dialogues(payload.dialogues)
                except ValueError as repair_error:
                    logger.warning('Unable to repair dialogues: %s', repair_error)
                    last_error = str(exc)
                    continue
                script = Script(title=payload.title, dialogues=repaired_dialogues)
                logger.info('Augmented structured payload with %s dialogue lines', len(script.dialogues))
            try:
                structured_yaml = self._dump_script_to_yaml(script)
            except ValueError as yaml_error:
                logger.warning('Generated structured script failed YAML validation: %s', yaml_error)
                last_error = str(yaml_error)
                continue
            metadata = payload.to_metadata()
            metadata.quality_report = self._compute_quality_report(script)
            return ScriptGenerationResult(
                script=script,
                metadata=metadata,
                raw_response=response_text,
                structured_yaml=structured_yaml,
            )
        if fallback_candidate:
            logger.warning('Returning fallback script after all attempts failed to parse YAML')
            return fallback_candidate
        logger.error('Structured script generation exhausted all attempts: %s', last_error or 'unknown error')
        backup_script = self._build_backup_script(news_items, target_duration_minutes)
        backup_report = self._compute_quality_report(backup_script)
        metadata = ScriptGenerationMetadata(quality_report=backup_report)
        structured_yaml = self._dump_script_to_yaml(backup_script)
        return ScriptGenerationResult(
            script=backup_script,
            metadata=metadata,
            raw_response='',
            structured_yaml=structured_yaml,
        )

    def _build_prompt(self, news_digest: str, target_duration_minutes: Optional[int]) -> str:
        speaker_list = ', '.join(self._allowed_speakers)
        duration_hint = f'目標尺はおよそ{target_duration_minutes}分です。' if target_duration_minutes else ''
        template = f'\n        以下の金融ニュース要約に基づき、視聴者が理解しやすい対話形式の台本を作成してください。\n\n        {duration_hint}\n\n        出力条件:\n        - 話者は必ず以下の名前のみを使用: {speaker_list}\n        - 各台詞は「{{speaker}}: {{line}}」形式にできる内容で、日本語で書く\n        - 行頭に話者名を付与し、会話を最低24ターン以上構成する\n        - 数値・視覚指示・行動提案を織り交ぜる\n        - YAML形式のマッピングのみで回答し、余計な文章やコードブロックは付けない\n\n        出力YAMLの例:\n        title: サンプルタイトル\n        summary: サマリー\n        dialogues:\n          - speaker: {self._allowed_speakers[0]}\n            line: 対話文\n        wow_score: 8.2\n        japanese_purity_score: 97.5\n        retention_prediction: 0.54\n\n        ニュース要約:\n        {news_digest}\n        '
        return textwrap.dedent(template).strip()

    def _parse_payload(self, response_text: str) -> StructuredScriptPayload:
        try:
            data = self._extract_structured_data(response_text)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        try:
            return StructuredScriptPayload.model_validate(data)
        except ValidationError as exc:
            raise ValueError(f'Structured payload validation failed: {exc}') from exc

    @staticmethod
    def _extract_message_text(response: Dict[str, Any]) -> str:
        return adapter_extract_message_text(response)

    def _extract_structured_data(self, response_text: str) -> Dict[str, Any]:
        errors = []
        yaml_block = self._extract_yaml_block(response_text)
        candidates = [candidate for candidate in (yaml_block, response_text) if candidate]

        for candidate in candidates:
            try:
                return self._load_yaml_mapping(candidate)
            except ValueError as exc:
                errors.append(exc)

        if errors:
            raise ValueError(f'No YAML mapping found in LLM response: {errors[-1]}')
        raise ValueError('No YAML mapping found in LLM response')

    @staticmethod
    def _extract_yaml_block(text: str) -> Optional[str]:
        match = re.search(r"```(?:yaml|yml)?\s*(.+?)```", text, flags=re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _load_yaml_mapping(text: str) -> Dict[str, Any]:
        try:
            decoded = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ValueError(f'Malformed YAML: {exc}') from exc

        if isinstance(decoded, dict):
            return decoded

        if isinstance(decoded, str):
            return StructuredScriptGenerator._load_yaml_mapping(decoded)

        raise ValueError(f'Unexpected YAML top-level type: {type(decoded).__name__}')

    def _build_script_from_text(self, response_text: str) -> Tuple[Script, ScriptQualityReport]:
        validation: Optional[ScriptValidationResult] = None
        try:
            validation = ensure_dialogue_structure(response_text, allowed_speakers=self._allowed_speakers, min_dialogue_lines=10)
        except ScriptFormatError as exc:
            validation = exc.result
            logger.debug('Dialogue structure issues: %s', exc)
        dialogues = self._dialogues_from_validation(validation)
        if dialogues:
            try:
                dialogues = self._ensure_min_dialogues(dialogues)
            except ValueError:
                dialogues = []
        if not dialogues:
            dialogues = self._fabricate_dialogues(response_text)
        title = self._infer_title(response_text)
        script = Script(title=title, dialogues=dialogues)
        quality_report = self._build_quality_report_from_validation(validation, script)
        return (script, quality_report)

    def _dialogues_from_validation(self, validation: Optional[ScriptValidationResult]) -> List[DialogueEntry]:
        if not validation:
            return []
        dialogues: List[DialogueEntry] = []
        for raw_line in validation.normalized_script.splitlines():
            stripped = raw_line.strip()
            if not stripped or ':' not in stripped:
                continue
            speaker, content = stripped.split(':', 1)
            speaker = self._canonicalize_speaker(speaker)
            content = content.strip() or '(内容未設定)'
            dialogues.append(DialogueEntry(speaker=speaker or self._allowed_speakers[len(dialogues) % len(self._allowed_speakers)], line=content))
        return dialogues

    def _fabricate_dialogues(self, response_text: str) -> List[DialogueEntry]:
        dialogues: List[DialogueEntry] = []
        for raw_line in response_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            speaker = None
            content = line
            if ':' in line:
                potential, remainder = line.split(':', 1)
                normalized_speaker = potential.strip()
                remainder = remainder.strip()
                if remainder:
                    speaker = self._canonicalize_speaker(normalized_speaker)
                    content = remainder
            if speaker is None:
                speaker = self._allowed_speakers[len(dialogues) % len(self._allowed_speakers)]
            if not content:
                content = '(内容未設定)'
            dialogues.append(DialogueEntry(speaker=speaker, line=content))
        if not dialogues:
            raise ValueError('No dialogue lines discovered in text output')
        if len(dialogues) == 1:
            alternate = self._allowed_speakers[1 % len(self._allowed_speakers)]
            dialogues.append(DialogueEntry(speaker=alternate, line='(補完台詞)'))
        return dialogues

    def _ensure_min_dialogues(self, dialogues: Sequence[DialogueEntry]) -> List[DialogueEntry]:
        if not dialogues:
            raise ValueError('Structured payload did not contain any dialogue lines')
        normalized = [DialogueEntry(speaker=entry.speaker, line=entry.line) for entry in dialogues]
        if len(normalized) >= 2:
            return normalized
        first_speaker = normalized[0].speaker or self._allowed_speakers[0]
        fallback_speaker: Optional[str] = None
        for candidate in self._allowed_speakers:
            if candidate and candidate != first_speaker:
                fallback_speaker = candidate
                break
        if not fallback_speaker:
            fallback_speaker = first_speaker or (self._allowed_speakers[0] if self._allowed_speakers else 'ナビゲーター')
        normalized.append(DialogueEntry(speaker=fallback_speaker, line='(補完台詞)'))
        return normalized

    def _canonicalize_speaker(self, label: Optional[str]) -> Optional[str]:
        if not label:
            return None
        normalized = label.strip()
        if not normalized:
            return None
        mapped = self._alias_lookup.get(normalized, normalized)
        if mapped in self._allowed_speaker_set:
            return mapped
        return None

    def _infer_title(self, response_text: str) -> str:
        for line in response_text.splitlines():
            candidate = line.strip()
            if not candidate:
                continue
            if candidate.startswith('{'):
                continue
            return candidate[:80]
        return '自動生成スクリプト'

    def _build_quality_report_from_validation(self, validation: Optional[ScriptValidationResult], script: Script) -> ScriptQualityReport:
        if not validation:
            return self._apply_roster_warnings(ScriptQualityReport(dialogue_lines=len(script.dialogues), total_nonempty_lines=len(script.dialogues), distinct_speakers=len({d.speaker for d in script.dialogues}), warnings=[], errors=[]))
        report = ScriptQualityReport(dialogue_lines=validation.dialogue_line_count, total_nonempty_lines=validation.nonempty_line_count, distinct_speakers=sum((1 for count in validation.speaker_counts.values() if count > 0)), warnings=[issue.message for issue in validation.warnings], errors=[issue.message for issue in validation.errors])
        actual_dialogues = len(script.dialogues)
        actual_nonempty = sum((1 for entry in script.dialogues if entry.line.strip()))
        actual_speakers = len({entry.speaker for entry in script.dialogues if entry.speaker})
        report = report.copy(update={'dialogue_lines': max(report.dialogue_lines, actual_dialogues), 'total_nonempty_lines': max(report.total_nonempty_lines, actual_nonempty), 'distinct_speakers': max(report.distinct_speakers, actual_speakers)})
        return self._apply_roster_warnings(report)

    def _compute_quality_report(self, script: Script) -> ScriptQualityReport:
        try:
            validation = ensure_dialogue_structure(script.to_text(), allowed_speakers=self._allowed_speakers, min_dialogue_lines=10)
        except ScriptFormatError as exc:
            validation = exc.result
        return self._build_quality_report_from_validation(validation, script)

    def _apply_roster_warnings(self, report: ScriptQualityReport) -> ScriptQualityReport:
        warning = self._speaker_roster.warning_message
        if not warning:
            return report
        existing = list(report.warnings)
        if warning in existing:
            return report
        existing.append(warning)
        return report.copy(update={'warnings': existing})

    def _dump_script_to_yaml(self, script: Script) -> str:
        payload = script.model_dump(mode='python')
        yaml_blob = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
        try:
            loaded = yaml.safe_load(yaml_blob)
        except yaml.YAMLError as exc:
            raise ValueError(f'Failed to validate structured script as YAML: {exc}') from exc
        if not isinstance(loaded, dict):
            raise ValueError('Structured script YAML must decode to a mapping')
        return yaml_blob

    def _build_backup_script(self, news_items: List[Dict[str, Any]], target_duration_minutes: Optional[int]=None) -> Script:
        topics: List[Dict[str, str]] = []
        for index, item in enumerate(news_items, start=1):
            topics.append({'title': str(item.get('title') or item.get('headline') or f'トピック{index}'), 'summary': str(item.get('summary') or item.get('description') or '市場動向の詳細は追加調査が必要です。'), 'impact': str(item.get('impact_level') or item.get('importance') or 'medium'), 'source': str(item.get('source') or '情報源不明')})
        if not topics:
            topics = [{'title': 'マーケット最新動向', 'summary': '主要指標とリスクイベントを振り返りながら今後の注意点を共有します。', 'impact': 'medium', 'source': '社内調査'}]
        primary = self._allowed_speakers[0]
        secondary = self._allowed_speakers[1]
        narrator = self._allowed_speakers[2] if len(self._allowed_speakers) > 2 else None
        dialogues: List[DialogueEntry] = []

        def add_dialogue(speaker: str, line: str) -> None:
            dialogues.append(DialogueEntry(speaker=speaker, line=line))
        duration_hint = f'尺はおよそ{target_duration_minutes}分を想定しています。' if target_duration_minutes else ''
        add_dialogue(primary, 'こんばんは、今日もマーケットの振り返りを始めましょう。')
        add_dialogue(secondary, 'よろしくお願いします。最初の注目トピックから教えてください。')
        if narrator:
            add_dialogue(narrator, duration_hint or '番組の流れを整理しながら解説します。')
        for idx, topic in enumerate(topics, start=1):
            add_dialogue(primary, f"{idx}つ目は『{topic['title']}』です。重要度は{topic['impact']}、情報源は{topic['source']}です。")
            add_dialogue(secondary, f"要点をまとめると、{topic['summary']}")
            add_dialogue(primary, '投資家として意識したいリスクとチャンスを整理していきましょう。')
            if narrator:
                add_dialogue(narrator, '視聴者の皆さんはご自身のポートフォリオでの影響度をチェックしてみてください。')
            add_dialogue(secondary, '短期的な値動きだけでなく、中長期の構造変化にも目を向けたいですね。')
            add_dialogue(primary, 'データポイントや企業コメントが更新されたら、概要欄のリンクでフォローしてください。')
        add_dialogue(secondary, '他にも気になる指標があればコメントで教えてください。追加解説を検討します。')
        add_dialogue(primary, '最後に具体的なアクションプランを3つまとめます。')
        add_dialogue(primary, '① ポジションサイズの見直し、② リスクイベント前のヘッジ、③ 指標速報のウォッチです。')
        if narrator:
            add_dialogue(narrator, '概要欄には参考リンクと免責事項を記載しています。投資判断はご自身でお願いします。')
        add_dialogue(secondary, '引き続き最新のマーケット情報をお届けしますので、チャンネル登録もお忘れなく。')
        add_dialogue(primary, 'ご視聴ありがとうございました。それではまた次回お会いしましょう。')
        while len(dialogues) < 24:
            speaker = self._allowed_speakers[len(dialogues) % len(self._allowed_speakers)]
            add_dialogue(speaker, '補足情報を追記し、マーケットの変化に備えましょう。')
        title_prefix = 'バックアップ台本'
        headline = topics[0]['title']
        title = f'{title_prefix}: {headline}'[:80]
        return Script(title=title, dialogues=dialogues)

    @staticmethod
    def _format_news_digest(news_items: List[Dict[str, Any]]) -> str:
        if not news_items:
            return '(ニュース項目が提供されていません)'
        lines: List[str] = []
        for index, item in enumerate(news_items, start=1):
            title = item.get('title') or item.get('headline') or f'ニュース{index}'
            summary = item.get('summary') or item.get('description') or '概要不明'
            source = item.get('source') or '不明'
            impact = item.get('impact_level') or item.get('importance') or 'medium'
            lines.append(textwrap.dedent(f'\n                    ■ {index}. {title}\n                       出典: {source} / 重要度: {impact}\n                       要約: {summary}\n                    ').strip())
        return '\n\n'.join(lines)
ScriptGenerationMetadata.model_rebuild()
