"""CrewAI タスク定義

エージェントに割り当てるタスクを設定駆動で生成
"""

import logging
from typing import Dict, List, Any, Optional
from crewai import Task, Agent

from app.config_prompts.settings import get_prompt_manager, render_prompt

logger = logging.getLogger(__name__)


class TaskFactory:
    """タスクファクトリー

    プロンプトYAMLからタスクを動的に生成
    """

    def __init__(self):
        self.prompt_manager = get_prompt_manager()

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
            task_template = self.prompt_manager.get_task_template(task_name)

            # プロンプトをレンダリング
            description = task_template.get('description', '')
            if context_data:
                # Jinja2でプレースホルダーを置換
                from jinja2 import Template
                template = Template(description)
                description = template.render(**context_data)

            expected_output = task_template.get('expected_output', '')

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
    tasks['task1_deep_analysis'] = factory.create_task(
        task_name='deep_news_analysis',
        agent=agents['deep_news_analyzer'],
        context_data={'news_items': news_summary}
    )

    # Task 2: Curiosity Gap Design
    tasks['task2_curiosity_gaps'] = factory.create_task(
        task_name='curiosity_gap_design',
        agent=agents['curiosity_gap_researcher'],
        context_data={
            'deep_analysis_result': '{{ task1結果をここに挿入 }}'
        },
        context_tasks=[tasks['task1_deep_analysis']]
    )

    # Task 3: Emotional Story Arc Design
    tasks['task3_story_arc'] = factory.create_task(
        task_name='emotional_story_arc_design',
        agent=agents['emotional_story_architect'],
        context_data={
            'deep_analysis_result': '{{ task1結果 }}',
            'curiosity_gaps': '{{ task2結果 }}'
        },
        context_tasks=[tasks['task1_deep_analysis'], tasks['task2_curiosity_gaps']]
    )

    # Task 4: Script Writing
    tasks['task4_script_writing'] = factory.create_task(
        task_name='script_writing',
        agent=agents['script_writer'],
        context_data={
            'surprise_points': '{{ task1結果 }}',
            'curiosity_gaps': '{{ task2結果 }}',
            'story_arc': '{{ task3結果 }}'
        },
        context_tasks=[
            tasks['task1_deep_analysis'],
            tasks['task2_curiosity_gaps'],
            tasks['task3_story_arc']
        ]
    )

    # Task 5: Engagement Optimization
    tasks['task5_engagement'] = factory.create_task(
        task_name='engagement_optimization',
        agent=agents['engagement_optimizer'],
        context_data={
            'first_draft_script': '{{ task4結果 }}'
        },
        context_tasks=[tasks['task4_script_writing']]
    )

    # Task 6: Quality Evaluation
    tasks['task6_quality'] = factory.create_task(
        task_name='quality_evaluation',
        agent=agents['quality_guardian'],
        context_data={
            'optimized_script': '{{ task5結果 }}'
        },
        context_tasks=[tasks['task5_engagement']]
    )

    # Task 7: Japanese Purity Check
    tasks['task7_japanese'] = factory.create_task(
        task_name='japanese_purity_check',
        agent=agents['japanese_purity_polisher'],
        context_data={
            'quality_approved_script': '{{ task6結果 }}',
            'quality_evaluation_result': '{{ task6評価結果 }}'
        },
        context_tasks=[tasks['task6_quality']]
    )

    logger.info(f"✅ Created {len(tasks)} tasks for WOW Script Creation Crew")
    return tasks
