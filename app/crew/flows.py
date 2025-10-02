"""CrewAI フロー定義

WOW Script Creation Crewの実行フローとオーケストレーション
"""

import logging
from typing import Dict, List, Any, Optional
from crewai import Crew, Process

from app.models import NewsCollection, Script, QualityScore
from app.config import cfg as settings
from .agents import create_wow_agents
from .tasks import create_wow_tasks

logger = logging.getLogger(__name__)


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

        # エージェント生成
        self.agents = create_wow_agents()

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
        # CrewAIの結果は通常文字列として返される
        # 最後のタスク（Japanese Purity Check）の出力を最終台本とする

        result = {
            'success': True,
            'final_script': str(crew_result),
            'crew_output': crew_result,
        }

        # TODO: JSON形式で返されている場合はパースして構造化データを抽出

        return result


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
