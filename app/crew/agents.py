"""CrewAI エージェント定義
7つの専門AIエージェントを設定駆動で生成
"""
import logging
from typing import Dict, Optional
from crewai import Agent
from app.config.settings import settings
from app.prompt_cache import get_prompt_manager
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
            agent_config = self.prompt_manager.get_agent_config(agent_name)
            overrides = dict(override_params)
            override_model = overrides.pop("model", None)
            override_temperature = overrides.pop("temperature", None)
            from app.crew.tools.ai_clients import get_crewai_gemini_llm
            base_temperature = agent_config.get("temperature", 0.7)
            llm_temperature = override_temperature if override_temperature is not None else base_temperature
            llm_model = override_model or agent_config.get("model") or settings.gemini_models.get("crew_agents")
            llm = get_crewai_gemini_llm(
                model=llm_model,
                temperature=llm_temperature,
            )
            agent = Agent(
                role=agent_config.get("role", agent_name),
                goal=agent_config.get("goal", ""),
                backstory=agent_config.get("backstory", ""),
                verbose=getattr(settings, "crew_verbose", False),
                llm=llm,
                **overrides,
            )
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
def create_wow_agents(gemini_model: Optional[str] = None) -> Dict[str, Agent]:
    """WOW Script Creation Crewの7エージェントを生成
    Returns:
        エージェント名 → Agentインスタンスの辞書
    """
    factory = AgentFactory()
    resolved_model = gemini_model or settings.gemini_models.get("crew_agents")
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
            agents[agent_name] = factory.create_agent(agent_name, model=resolved_model)
        except Exception as e:
            logger.error(f"Failed to create required agent '{agent_name}': {e}")
            raise RuntimeError(f"Cannot create WOW agents without '{agent_name}'")
    logger.info("✅ WOW Script Creation Crew: All 7 agents created successfully")
    return agents
