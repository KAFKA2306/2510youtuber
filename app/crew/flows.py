"""CrewAI フロー定義

WOW Script Creation Crewの実行フローとオーケストレーション
"""

import ast
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from crewai import Crew, Process

from app.config import cfg as settings

from .agent_review import AgentReviewCycle
from .agents import create_wow_agents
from .tasks import create_wow_tasks

logger = logging.getLogger(__name__)

# Configure LiteLLM to work with Google AI Studio (not Vertex AI)
import litellm

from app.api_rotation import get_rotation_manager

# Configure LiteLLM settings
litellm.drop_params = True  # Drop unknown parameters
litellm.suppress_debug_info = False  # Keep debug for now
litellm.vertex_project = None  # Force no Vertex project
litellm.vertex_location = None  # Force no Vertex location

# Patch LiteLLM completion to use shared rotation manager
original_completion = litellm.completion


def patched_completion(model=None, messages=None, **kwargs):
    """Intercept LiteLLM completion calls to use shared rotation manager"""
    if model and "gemini" in model.lower() and "/" not in model:
        # 統一モデル名に変換（未プレフィックス時のみ）
        forced_model = f"gemini/{settings.gemini_models.get('crew_agents')}"
        if model != forced_model:
            logger.debug(f"LiteLLM completion intercepted: {model} -> {forced_model}")
        model = forced_model

    # Remove any Vertex AI credentials from kwargs
    kwargs.pop("vertex_credentials", None)
    kwargs.pop("vertex_project", None)
    kwargs.pop("vertex_location", None)

    # Use shared rotation manager
    rotation_manager = get_rotation_manager()

    def litellm_call(api_key: str):
        """Single API call with given key"""
        os.environ["GEMINI_API_KEY"] = api_key
        return original_completion(model=model, messages=messages, **kwargs)

    # Execute with rotation
    return rotation_manager.execute_with_rotation(provider="gemini", api_call=litellm_call, max_attempts=3)


litellm.completion = patched_completion

logger.info("Configured LiteLLM: Using shared rotation manager, Vertex AI blocked")


class WOWScriptFlow:
    """WOW Script Creation Crewの実行フロー

    7つのエージェントと7つのタスクを適切な順序で実行し、
    品質基準を満たす台本を生成
    """

    def __init__(self):
        self.max_quality_iterations = getattr(settings, "max_quality_iterations", 2)
        self.agents = None
        self.tasks = None
        self.review_cycle = AgentReviewCycle()

    def initialize(self, news_items: List[Dict[str, Any]]):
        """エージェントとタスクを初期化

        Args:
            news_items: ニュース項目リスト
        """
        logger.info("Initializing WOW Script Creation Crew...")

        # エージェント生成 (統一モデル名を指定)
        self.agents = create_wow_agents()

        improvement_notes = self.review_cycle.prepare_improvement_notes()

        # タスク生成
        self.tasks = create_wow_tasks(self.agents, news_items, improvement_notes=improvement_notes)

        logger.info("✅ WOW Script Creation Crew initialized")

    def execute(self, news_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """フル実行

        Args:
            news_items: ニュース項目リスト

        Returns:
            実行結果（最終台本、品質スコアなど）
        """
        # 初期化
        self.initialize(news_items)

        # Crewを作成
        crew = Crew(
            agents=list(self.agents.values()),
            tasks=list(self.tasks.values()),
            process=Process.sequential,  # 順次実行
            verbose=getattr(settings, "crew_verbose", False),
        )

        logger.info("🚀 Starting WOW Script Creation Crew execution...")

        try:
            # 実行
            result = crew.kickoff()

            review_results = self.review_cycle.run(self.tasks)

            logger.info("✅ WOW Script Creation Crew completed successfully")

            # 結果をパース
            final_result = self._parse_crew_result(result)

            script_candidate = str(final_result.get("final_script", "")).strip()
            if not self._looks_like_dialogue(script_candidate):
                fallback_script, source = self._extract_fallback_script()
                if fallback_script:
                    logger.warning(
                        "Crew output lacked dialogue structure; using %s draft instead",
                        source,
                    )
                    final_result["final_script"] = fallback_script
                    final_result.setdefault("metadata", {})
                    final_result["metadata"]["fallback_source"] = source

            if review_results:
                final_result["agent_reviews"] = {
                    key: review.model_dump(mode="json") for key, review in review_results.items()
                }

            return final_result

        except Exception as e:
            logger.error(f"❌ WOW Script Creation Crew failed: {e}")
            raise

    def _parse_crew_result(self, crew_result: Any) -> Dict[str, Any]:
        """Crew実行結果をパース

        Args:
            crew_result: Crewの実行結果

        Returns:
            構造化された結果辞書
        """
        # CrewAIの結果は通常文字列として返される
        # 最後のタスク（Japanese Purity Check）の出力を最終台本とする
        crew_output_str = str(crew_result)

        # JSON形式で返されている場合はパースして構造化データを抽出
        try:
            # ```json ... ``` のパターンを探す
            json_match = re.search(r"```json\n(.*?)\n```", crew_output_str, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                # JSONをパース
                parsed_data = json.loads(json_str)
            else:
                parsed_data = None
                stripped_output = crew_output_str.strip()

                if (stripped_output.startswith("'") and stripped_output.endswith("'")) or (
                    stripped_output.startswith('"') and stripped_output.endswith('"')
                ):
                    try:
                        decoded_output = ast.literal_eval(stripped_output)
                        if isinstance(decoded_output, str):
                            stripped_output = decoded_output.strip()
                    except (ValueError, SyntaxError):
                        pass

                if stripped_output.startswith("{"):
                    try:
                        parsed_data = json.loads(stripped_output)
                        logger.debug("Parsed CrewAI output as raw JSON block")
                    except json.JSONDecodeError as exc:
                        parsed_data = None
                        logger.debug("Raw JSON parse failed: %s", exc)

                if parsed_data is None and "{" in stripped_output and "}" in stripped_output:
                    candidate = stripped_output[stripped_output.find("{") : stripped_output.rfind("}") + 1]
                    try:
                        parsed_data = json.loads(candidate)
                        logger.debug("Parsed CrewAI output from embedded JSON snippet")
                    except json.JSONDecodeError as exc:
                        parsed_data = None
                        logger.debug("Embedded JSON parse failed: %s", exc)

                if parsed_data is not None:
                    crew_output_str = stripped_output
            if parsed_data is None:
                logger.warning("No JSON found in CrewAI output, using raw text")
                logger.warning("Failed to locate JSON payload in CrewAI output; returning raw text")
                cleaned_output = re.sub(r"```json\s*", "", crew_output_str)
                cleaned_output = re.sub(r"```\s*", "", cleaned_output)
                snippet = cleaned_output.strip()[:400]
                logger.info(
                    "First 400 chars of raw CrewAI output: %r",
                    snippet,
                )
                return {
                    "success": True,
                    "final_script": cleaned_output.strip(),
                    "crew_output": crew_output_str,
                }

            # final_scriptフィールドを抽出
            final_script = parsed_data.get("final_script", crew_output_str)

            logger.info(f"Successfully parsed CrewAI JSON output, script length: {len(final_script)}")
            logger.info(f"First 800 chars of parsed script: {final_script[:800]}")

            # Verify each line of the script has speaker format (武宏:, つむぎ:, ナレーター:)
            # 設定から話者名を動的に取得
            from app.config.settings import settings

            speaker_names = [s.name for s in settings.speakers]
            # 後方互換性のため旧話者名もサポート
            legacy_speakers = ["田中", "鈴木", "司会"]
            all_speakers = speaker_names + legacy_speakers
            speaker_pattern_str = "|".join(re.escape(name) for name in all_speakers)
            speaker_pattern = re.compile(rf"^({speaker_pattern_str})\s*([:：])\s*([^:：].*)")
            script_lines = final_script.strip().split("\n")

            speaker_format_valid = True
            for i, line in enumerate(script_lines):
                if line.strip() and not speaker_pattern.match(line.strip()):
                    speaker_format_valid = False
                    break  # 最初の無効な行が見つかったらループを抜ける

            if not speaker_format_valid:
                logger.warning("Script does not have proper speaker format")
                logger.warning("This indicates CrewAI did not follow the output format instructions.")

            result = {
                "success": True,
                "final_script": final_script,
                "crew_output": parsed_data,
                "quality_data": parsed_data.get("quality_guarantee", {}),
                "japanese_purity_score": parsed_data.get("japanese_purity_score", 0),
                "character_count": parsed_data.get("character_count", len(final_script)),
                "speaker_format_valid": speaker_format_valid,  # 新しいフィールドを追加
            }

            return result

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse CrewAI output as JSON: {e}, using raw text")
            return {
                "success": True,
                "final_script": crew_output_str,
                "crew_output": crew_output_str,
            }

    def _extract_fallback_script(self) -> tuple[Optional[str], str]:
        fallback_order = [
            ("task7_japanese", "japanese_purity_polisher"),
            ("task6_quality", "quality_guardian"),
            ("task5_engagement", "engagement_optimizer"),
            ("task4_script_writing", "script_writer"),
        ]

        for task_key, label in fallback_order:
            script = self._get_task_output(task_key)
            if script and self._looks_like_dialogue(script):
                return script, label
            if script:
                logger.info(
                    "Fallback candidate %s preview=%r",
                    label,
                    str(script)[:160],
                )
        return None, ""

    def _get_task_output(self, task_key: str) -> Optional[str]:
        task = (self.tasks or {}).get(task_key)
        if not task:
            return None
        output = getattr(task, "output", None)
        raw = getattr(output, "raw", None)
        if raw:
            text = str(raw).strip()
            normalized = self._extract_script_text_from_string(text)
            return normalized or text
        return None

    @staticmethod
    def _extract_script_text_from_string(payload: str) -> Optional[str]:
        if not payload:
            return None

        text = payload.strip()

        if text.startswith("Message(") and "content=" in text:
            match = re.search(r"content=(.+?)\)\z", text, re.DOTALL)
            if match:
                candidate = match.group(1).strip()
                try:
                    decoded = ast.literal_eval(candidate)
                    if isinstance(decoded, str):
                        text = decoded.strip()
                except (ValueError, SyntaxError):
                    pass

        if text.startswith("```json"):
            text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"```\s*$", "", text)

        if text.startswith("{"):
            try:
                data = json.loads(text)
                final_script = data.get("final_script") or data.get("script") or data.get("draft")
                if isinstance(final_script, str):
                    return final_script.strip()
                dialogues = data.get("dialogues")
                if isinstance(dialogues, list):
                    try:
                        lines = [
                            f"{entry['speaker']}: {entry['line']}"
                            for entry in dialogues
                            if isinstance(entry, dict) and entry.get("speaker") and entry.get("line")
                        ]
                        if lines:
                            return "\n".join(lines).strip()
                    except KeyError:
                        pass
            except json.JSONDecodeError:
                return None

        return None

    @staticmethod
    def _looks_like_dialogue(script_text: str) -> bool:
        if not script_text:
            return False
        lines = [line.strip() for line in script_text.splitlines() if line.strip()]
        if len(lines) < 4:
            return False
        if lines[0].startswith("{") or lines[0].startswith('"'):
            return False
        dialogue_lines = [line for line in lines if re.match(r"^[^:：\s]{1,16}[：:]", line)]
        return len(dialogue_lines) >= 4


def create_wow_script_crew(news_items: List[Dict[str, Any]], target_duration_minutes: int = 8) -> Dict[str, Any]:
    """WOW Script Creation Crewを実行（簡易関数）

    Args:
        news_items: ニュース項目リスト
        target_duration_minutes: 目標動画長（分）

    Returns:
        実行結果
    """
    flow = WOWScriptFlow()
    return flow.execute(news_items)


class WOWScriptFlowWithQualityLoop:
    """品質チェックループ付きWOW Script Flow

    WOWスコアが基準未達の場合、自動的に再生成
    """

    def __init__(self):
        self.max_iterations = getattr(settings, "max_quality_iterations", 2)
        self.wow_threshold = getattr(settings, "wow_score_min", 8.0)

    def execute_with_quality_loop(self, news_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """品質ループ付き実行

        Args:
            news_items: ニュース項目リスト

        Returns:
            品質基準を満たした最終結果
        """
        iteration = 0

        while iteration < self.max_iterations:
            logger.info(f"Quality loop iteration {iteration + 1}/{self.max_iterations}")

            # Crew実行
            flow = WOWScriptFlow()
            result = flow.execute(news_items)

            # 品質評価
            # TODO: 実際の品質スコアを抽出
            wow_score = result.get("wow_score", 0.0)

            if wow_score >= self.wow_threshold:
                logger.info(f"✅ Quality threshold met: WOW Score = {wow_score}")
                result["iterations"] = iteration + 1
                return result

            logger.warning(f"⚠️ Quality threshold not met: {wow_score} < {self.wow_threshold}")
            iteration += 1

        # 最大反復回数到達
        logger.warning(f"Max iterations ({self.max_iterations}) reached")
        result["iterations"] = self.max_iterations
        result["quality_warning"] = "Max iterations reached without meeting threshold"
        return result
