"""CrewAI タスク定義

エージェントに割り当てるタスクを設定駆動で生成
"""

import logging
from typing import Any, Dict, List, Optional

from crewai import Agent, Task

from app.config_prompts.settings import settings

logger = logging.getLogger(__name__)


class TaskFactory:
    """タスクファクトリー

    プロンプトYAMLからタスクを動的に生成
    """

    def __init__(self):
        self.prompt_manager = settings.prompt_manager

    def create_task(
        self,
        task_name: str,
        agent: Agent,
        context_data: Optional[Dict[str, Any]] = None,
        context_tasks: Optional[List[Task]] = None,
        **override_params
    ) -> Task:
        """単一タスクを生成

        Args:
            task_name: タスク名（YAML内のキー）
            agent: 担当エージェント
            context_data: プロンプトに渡すデータ
            context_tasks: 依存する先行タスク
            **override_params: パラメータ上書き

        Returns:
            Taskインスタンス
        """
        try:
            # タスクテンプレートを取得
            task_template_content = self.prompt_manager.get_prompt_template(task_name)

            # プロンプトをレンダリング
            description = task_template_content
            if context_data:
                # Jinja2でプレースホルダーを置換
                description = self.prompt_manager.render_prompt(task_name, context_data)

            # expected_outputは別途定義が必要な場合があるため、ここでは空とするか、テンプレートから取得するロジックを追加
            # 現状のYAML構造ではexpected_outputが直接テンプレートに含まれていないため、一旦空とする
            expected_output = override_params.pop("expected_output", "") # override_paramsから取得

            # タスク作成
            task = Task(
                description=description,
                expected_output=expected_output,
                agent=agent,
                context=context_tasks or [],
                **override_params
            )

            logger.debug(f"Created task: {task_name}")
            return task

        except Exception as e:
            logger.error(f"Failed to create task '{task_name}': {e}")
            raise


def create_wow_tasks(
    agents: Dict[str, Agent],
    news_items: List[Dict[str, Any]]
) -> Dict[str, Task]:
    """WOW Script Creation Crewの全タスクを生成

    Args:
        agents: エージェント辞書
        news_items: ニュース項目リスト

    Returns:
        タスク名 → Taskインスタンスの辞書
    """
    factory = TaskFactory()
    tasks = {}

    # ニュース項目を文字列化
    news_summary = "\n\n".join([
        f"■ {i+1}. {item.get('title', 'タイトルなし')}\n"
        f"   出典: {item.get('source', '不明')}\n"
        f"   要約: {item.get('summary', '')}\n"
        f"   重要度: {item.get('impact_level', 'medium')}"
        for i, item in enumerate(news_items)
    ])

    # Task 1: Deep News Analysis
    tasks["task1_deep_analysis"] = factory.create_task(
        task_name="analysis", # agents.yamlのキーに合わせる
        agent=agents["deep_news_analyzer"],
        context_data={"news_items": news_summary},
        expected_output="詳細なニュース分析結果" # expected_outputを明示的に渡す
    )

    # Task 2: Curiosity Gap Design
    tasks["task2_curiosity_gaps"] = factory.create_task(
        task_name="analysis", # agents.yamlのキーに合わせる
        agent=agents["curiosity_gap_researcher"],
        context_data={
            "deep_analysis_result": "{{ task1_deep_analysis.output }}" # CrewAIのタスク出力参照形式
        },
        context_tasks=[tasks["task1_deep_analysis"]],
        expected_output="視聴者の好奇心を刺激するギャップのリスト"
    )

    # Task 3: Emotional Story Arc Design
    tasks["task3_story_arc"] = factory.create_task(
        task_name="analysis", # agents.yamlのキーに合わせる
        agent=agents["emotional_story_architect"],
        context_data={
            "deep_analysis_result": "{{ task1_deep_analysis.output }}",
            "curiosity_gaps": "{{ task2_curiosity_gaps.output }}"
        },
        context_tasks=[tasks["task1_deep_analysis"], tasks["task2_curiosity_gaps"]],
        expected_output="感情的なストーリーアークの設計"
    )

    # Task 4: Script Writing
    tasks["task4_script_writing"] = factory.create_task(
        task_name="script_generation", # script_generation.yamlのキーに合わせる
        agent=agents["script_writer"],
        context_data={
            "surprise_points": "{{ task1_deep_analysis.output }}", # 適切な出力に修正
            "curiosity_gaps": "{{ task2_curiosity_gaps.output }}",
            "story_arc": "{{ task3_story_arc.output }}"
        },
        context_tasks=[
            tasks["task1_deep_analysis"],
            tasks["task2_curiosity_gaps"],
            tasks["task3_story_arc"]
        ],
        expected_output="高品質な動画スクリプト"
    )

    # Task 5: Engagement Optimization
    tasks["task5_engagement"] = factory.create_task(
        task_name="quality_check", # quality_check.yamlのキーに合わせる
        agent=agents["engagement_optimizer"],
        context_data={
            "first_draft_script": "{{ task4_script_writing.output }}"
        },
        context_tasks=[tasks["task4_script_writing"]],
        expected_output="エンゲージメント最適化されたスクリプト"
    )

    # Task 6: Quality Evaluation
    tasks["task6_quality"] = factory.create_task(
        task_name="quality_check", # quality_check.yamlのキーに合わせる
        agent=agents["quality_guardian"],
        context_data={
            "optimized_script": "{{ task5_engagement.output }}"
        },
        context_tasks=[tasks["task5_engagement"]],
        expected_output="スクリプトの品質評価レポート"
    )

    # Task 7: Japanese Purity Check
    tasks["task7_japanese"] = factory.create_task(
        task_name="quality_check", # quality_check.yamlのキーに合わせる
        agent=agents["japanese_purity_polisher"],
        context_data={
            "quality_approved_script": "{{ task6_quality.output }}", # 適切な出力に修正
            "quality_evaluation_result": "{{ task6_quality.output }}" # 適切な出力に修正
        },
        context_tasks=[tasks["task6_quality"]],
        expected_output="日本語純度チェック結果と修正案"
    )

    logger.info(f"✅ Created {len(tasks)} tasks for WOW Script Creation Crew")
    return tasks
