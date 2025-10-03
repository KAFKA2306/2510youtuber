"""CrewAI フロー定義

WOW Script Creation Crewの実行フローとオーケストレーション
"""

import logging
import os
from typing import Dict, List, Any, Optional
from crewai import Crew, Process

from app.models import NewsCollection, Script, QualityScore
from app.config import cfg as settings
from .agents import create_wow_agents
from .tasks import create_wow_tasks

logger = logging.getLogger(__name__)

# Configure LiteLLM to work with Google AI Studio (not Vertex AI)
import litellm

# CRITICAL: Force Google AI Studio by completely disabling Vertex AI detection
# This MUST happen before any LiteLLM imports or calls
os.environ.pop('GOOGLE_APPLICATION_CREDENTIALS', None)
os.environ.pop('VERTEX_PROJECT', None)
os.environ.pop('VERTEX_LOCATION', None)
os.environ.pop('GOOGLE_CLOUD_PROJECT', None)
os.environ.pop('GCLOUD_PROJECT', None)
os.environ.pop('GCP_PROJECT', None)

# Set initial GEMINI_API_KEY for LiteLLM
# LiteLLM will use this key, but we'll implement rotation on 429 errors
if settings.gemini_api_key:
    os.environ['GEMINI_API_KEY'] = settings.gemini_api_key

# Configure LiteLLM settings
litellm.drop_params = True  # Drop unknown parameters
litellm.suppress_debug_info = False  # Keep debug for now
litellm.vertex_project = None  # Force no Vertex project
litellm.vertex_location = None  # Force no Vertex location

# CRITICAL: Patch the model_cost calculation to prevent Vertex AI routing
# LiteLLM uses get_llm_provider internally which can still route to Vertex
original_completion = litellm.completion

# Key rotation state
_current_key_index = 0
_gemini_keys = [settings.gemini_api_key] if settings.gemini_api_key else []
# Add rotation keys
for i in range(2, 10):
    key = os.getenv(f"GEMINI_API_KEY_{i}")
    if key:
        _gemini_keys.append(key)

logger.info(f"Initialized {len(_gemini_keys)} Gemini API keys for rotation")

def patched_completion(model=None, messages=None, **kwargs):
    """Intercept all LiteLLM completion calls and force gemini/ prefix and model name with key rotation"""
    global _current_key_index

    if model and "gemini" in model.lower():
        # モデル名をgemini-2.5-flash-liteに強制
        forced_model = "gemini/gemini-2.5-flash-lite"
        if model != forced_model:
            logger.debug(f"LiteLLM completion intercepted: {model} -> {forced_model} (forced)")
        model = forced_model

    # Remove any Vertex AI credentials from kwargs
    kwargs.pop('vertex_credentials', None)
    kwargs.pop('vertex_project', None)
    kwargs.pop('vertex_location', None)

    # Try with current key, rotate on 429
    max_attempts = min(len(_gemini_keys), 5)
    last_error = None

    for attempt in range(max_attempts):
        try:
            # Set current API key
            if _gemini_keys:
                current_key = _gemini_keys[_current_key_index % len(_gemini_keys)]
                os.environ['GEMINI_API_KEY'] = current_key

            result = original_completion(model=model, messages=messages, **kwargs)
            return result

        except Exception as e:
            error_str = str(e).lower()
            is_rate_limit = any(keyword in error_str for keyword in ["429", "rate limit", "quota", "resource_exhausted"])

            if is_rate_limit and attempt < max_attempts - 1:
                _current_key_index = (_current_key_index + 1) % len(_gemini_keys)
                logger.warning(f"Gemini rate limit hit, rotating to key {_current_key_index + 1}/{len(_gemini_keys)}")
                last_error = e
                continue
            else:
                raise e

    if last_error:
        raise last_error

litellm.completion = patched_completion

logger.info("Configured LiteLLM: Vertex AI blocked, Google AI Studio forced")


class WOWScriptFlow:
    """WOW Script Creation Crewの実行フロー

    7つのエージェントと7つのタスクを適切な順序で実行し、
    品質基準を満たす台本を生成
    """

    def __init__(self):
        self.max_quality_iterations = getattr(settings, 'max_quality_iterations', 2)
        self.agents = None
        self.tasks = None

    def initialize(self, news_items: List[Dict[str, Any]]):
        """エージェントとタスクを初期化

        Args:
            news_items: ニュース項目リスト
        """
        logger.info("Initializing WOW Script Creation Crew...")

        # エージェント生成 (モデル名を明示的に指定)
        self.agents = create_wow_agents(gemini_model="gemini-2.5-flash-lite")

        # タスク生成
        self.tasks = create_wow_tasks(self.agents, news_items)

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
            verbose=getattr(settings, 'crew_verbose', False)
        )

        logger.info("🚀 Starting WOW Script Creation Crew execution...")

        try:
            # 実行
            result = crew.kickoff()

            logger.info("✅ WOW Script Creation Crew completed successfully")

            # 結果をパース
            final_result = self._parse_crew_result(result)

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
        import json
        import re

        # CrewAIの結果は通常文字列として返される
        # 最後のタスク（Japanese Purity Check）の出力を最終台本とする
        crew_output_str = str(crew_result)

        # JSON形式で返されている場合はパースして構造化データを抽出
        try:
            # ```json ... ``` のパターンを探す
            json_match = re.search(r'```json\n(.*?)\n```', crew_output_str, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                # JSONをパース
                parsed_data = json.loads(json_str)
            else:
                # JSONが見つからない場合は生のテキストを使用
                logger.warning("No JSON found in CrewAI output, using raw text")

                # JSONマーカーを削除（```json や ``` が残っている場合）
                cleaned_output = re.sub(r'```json\s*', '', crew_output_str)
                cleaned_output = re.sub(r'```\s*', '', cleaned_output)

                return {
                    'success': True,
                    'final_script': cleaned_output.strip(),
                    'crew_output': crew_result,
                }

            # final_scriptフィールドを抽出
            final_script = parsed_data.get('final_script', crew_output_str)

            logger.info(f"Successfully parsed CrewAI JSON output, script length: {len(final_script)}")
            logger.info(f"First 800 chars of parsed script: {final_script[:800]}")

            # Verify each line of the script has speaker format (田中:, 鈴木:, ナレーター:)
            speaker_pattern = re.compile(r"^(田中|鈴木|ナレーター|司会)\s*([:：])\s*([^:：].*)")
            script_lines = final_script.strip().split('\n')
            
            speaker_format_valid = True
            for i, line in enumerate(script_lines):
                if line.strip() and not speaker_pattern.match(line.strip()):
                    speaker_format_valid = False
                    break # 最初の無効な行が見つかったらループを抜ける
            
            if not speaker_format_valid:
                logger.warning("Script does not have proper speaker format")
                logger.warning("This indicates CrewAI did not follow the output format instructions.")

            result = {
                'success': True,
                'final_script': final_script,
                'crew_output': crew_result,
                'quality_data': parsed_data.get('quality_guarantee', {}),
                'japanese_purity_score': parsed_data.get('japanese_purity_score', 0),
                'character_count': parsed_data.get('character_count', len(final_script)),
                'speaker_format_valid': speaker_format_valid, # 新しいフィールドを追加
            }

            return result

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse CrewAI output as JSON: {e}, using raw text")
            return {
                'success': True,
                'final_script': crew_output_str,
                'crew_output': crew_result,
            }


def create_wow_script_crew(
    news_items: List[Dict[str, Any]],
    target_duration_minutes: int = 8
) -> Dict[str, Any]:
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
        self.max_iterations = getattr(settings, 'max_quality_iterations', 2)
        self.wow_threshold = getattr(settings, 'wow_score_min', 8.0)

    def execute_with_quality_loop(
        self,
        news_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
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
            wow_score = result.get('wow_score', 0.0)

            if wow_score >= self.wow_threshold:
                logger.info(f"✅ Quality threshold met: WOW Score = {wow_score}")
                result['iterations'] = iteration + 1
                return result

            logger.warning(f"⚠️ Quality threshold not met: {wow_score} < {self.wow_threshold}")
            iteration += 1

        # 最大反復回数到達
        logger.warning(f"Max iterations ({self.max_iterations}) reached")
        result['iterations'] = self.max_iterations
        result['quality_warning'] = "Max iterations reached without meeting threshold"
        return result
