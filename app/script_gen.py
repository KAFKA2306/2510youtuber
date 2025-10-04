# app/script_gen.py
"""
Script Generation Module
CrewAIを使った台本生成ロジック
"""

import logging
from typing import Any, Dict

from app.crew.flows import create_wow_script_crew
from app.crew.tools.ai_clients import GeminiClient
from app.models.workflow import Script

logger = logging.getLogger(__name__)


class ScriptGenerator:
    """台本生成を管理するクラス"""

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        self.client = GeminiClient(api_key=api_key, model=model)

    def generate_simple(self, prompt: str, config: Dict[str, Any] = None) -> str:
        """
        Geminiを直接呼び出す簡易生成（デバッグ用）
        """
        try:
            # ❌ timeout=120 は削除
            result = self.client.generate(prompt, generation_config=config)
            return result
        except Exception as e:
            logger.error(f"Simple script generation failed: {e}")
            raise

    def generate_with_crewai(self, news_items: list) -> Script:
        """
        CrewAIを使ってWOWスクリプトを生成する

        Args:
            news_items: ニュース要約のリスト
        Returns:
            Scriptオブジェクト
        """
        try:
            crew_result = create_wow_script_crew(news_items)
            if not isinstance(crew_result, Script):
                raise ValueError(f"CrewAI did not return Script, got {type(crew_result)}")
            return crew_result
        except Exception as e:
            logger.error(f"CrewAI script generation failed: {e}")
            raise
