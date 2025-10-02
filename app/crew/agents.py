"""CrewAI エージェント定義

7つの専門AIエージェントを設定駆動で生成
"""

import logging
import os # 追加
from typing import Dict, List, Optional
from crewai import Agent

from app.config import cfg as settings
from app.config_prompts.prompts import get_prompt_manager
from app.crew.tools import AIClientFactory

logger = logging.getLogger(__name__)


class AgentFactory:
    """エージェントファクトリー

    設定ファイルとプロンプトYAMLから動的にエージェントを生成
    """

    def __init__(self):
        self.prompt_manager = get_prompt_manager()

    def create_agent(self, agent_name: str, **override_params) -> Agent:
        """単一エージェントを生成

        Args:
            agent_name: エージェント名（agents.yamlで定義）
            **override_params: パラメータ上書き

        Returns:
            Agentインスタンス
        """
        try:
            # agents.yamlからエージェント設定を取得
            agent_config = self.prompt_manager.get_agent_config(agent_name)

            # LiteLLMがGoogle AI Studio APIを使用するように環境変数を設定
            # AgentがLLMを初期化する前に設定する必要がある
            # まず、Vertex AI関連のLiteLLM環境変数をクリア
            if "LITELLM_GEMINI_PROJECT" in os.environ:
                del os.environ["LITELLM_GEMINI_PROJECT"]
            if "LITELLM_GEMINI_LOCATION" in os.environ:
                del os.environ["LITELLM_GEMINI_LOCATION"]

            os.environ["LITELLM_MODEL"] = f"gemini/{agent_config.get('model', 'gemini-2.0-flash-exp')}"
            os.environ["LITELLM_API_KEY"] = settings.gemini_api_key
            os.environ["LITELLM_API_BASE"] = "https://generativelanguage.googleapis.com/v1beta"

            # AI Clientを生成
            llm = AIClientFactory.create_from_agent_config(agent_name)

            # エージェント作成
            agent = Agent(
                role=agent_config.get('role', agent_name),
                goal=agent_config.get('goal', ''),
                backstory=agent_config.get('backstory', ''),
                verbose=getattr(settings, 'crew_verbose', False),
                llm=llm,
                **override_params
            )
            
            # 環境変数をクリーンアップ
            if "LITELLM_MODEL" in os.environ:
                del os.environ["LITELLM_MODEL"]
            if "LITELLM_API_KEY" in os.environ:
                del os.environ["LITELLM_API_KEY"]
            if "LITELLM_API_BASE" in os.environ:
                del os.environ["LITELLM_API_BASE"]
            if "LITELLM_GEMINI_PROJECT" in os.environ:
                del os.environ["LITELLM_GEMINI_PROJECT"]
            if "LITELLM_GEMINI_LOCATION" in os.environ:
                del os.environ["LITELLM_GEMINI_LOCATION"]

            logger.info(f"Created agent: {agent_name}")
            return agent

        except Exception as e:
            logger.error(f"Failed to create agent '{agent_name}': {e}")
            raise

    def create_all_agents(self) -> Dict[str, Agent]:
        """全エージェントを生成

        Returns:
            エージェント名 → Agentインスタンスの辞書
        """
        agents_data = self.prompt_manager.load("agents.yaml")
        agent_names = list(agents_data.get("agents", {}).keys())

        agents = {}
        for name in agent_names:
            try:
                agents[name] = self.create_agent(name)
            except Exception as e:
                logger.warning(f"Skipping agent '{name}' due to error: {e}")

        logger.info(f"Created {len(agents)}/{len(agent_names)} agents")
        return agents


def create_wow_agents() -> Dict[str, Agent]:
    """WOW Script Creation Crewの7エージェントを生成

    Returns:
        エージェント名 → Agentインスタンスの辞書
    """
    factory = AgentFactory()

    # 必須の7エージェント
    required_agents = [
        "deep_news_analyzer",
        "curiosity_gap_researcher",
        "emotional_story_architect",
        "script_writer",
        "engagement_optimizer",
        "quality_guardian",
        "japanese_purity_polisher",
    ]

    agents = {}
    for agent_name in required_agents:
        try:
            agents[agent_name] = factory.create_agent(agent_name)
        except Exception as e:
            logger.error(f"Failed to create required agent '{agent_name}': {e}")
            raise RuntimeError(f"Cannot create WOW agents without '{agent_name}'")

    logger.info("✅ WOW Script Creation Crew: All 7 agents created successfully")
    return agents
