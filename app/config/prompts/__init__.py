"""プロンプト管理モジュール

YAMLファイルからプロンプトテンプレートを読み込み、
動的に変数を置換して使用します。
"""

from pathlib import Path
from typing import Dict, Any, Optional
import yaml
from jinja2 import Template


class PromptManager:
    """プロンプト管理クラス"""

    def __init__(self, prompts_dir: str = "app/config/prompts"):
        self.prompts_dir = Path(prompts_dir)
        self._cache: Dict[str, Dict[str, Any]] = {}

    def load(self, filename: str) -> Dict[str, Any]:
        """YAMLファイルを読み込み"""
        cache_key = filename
        if cache_key in self._cache:
            return self._cache[cache_key]

        file_path = self.prompts_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        self._cache[cache_key] = data
        return data

    def get_template(self, filename: str, template_name: str) -> str:
        """テンプレート文字列を取得"""
        data = self.load(filename)
        template_str = data.get(template_name)
        if template_str is None:
            raise ValueError(f"Template '{template_name}' not found in {filename}")
        return template_str

    def render(self, filename: str, template_name: str, **variables) -> str:
        """テンプレートを変数置換してレンダリング"""
        template_str = self.get_template(filename, template_name)
        template = Template(template_str)
        return template.render(**variables)

    def get_agent_config(self, agent_name: str) -> Dict[str, Any]:
        """エージェント設定を取得"""
        agents_data = self.load("agents.yaml")
        agent_config = agents_data.get("agents", {}).get(agent_name)
        if agent_config is None:
            raise ValueError(f"Agent '{agent_name}' not found in agents.yaml")
        return agent_config

    def get_task_template(self, task_name: str) -> Dict[str, Any]:
        """タスクテンプレートを取得"""
        # タスク定義は複数のYAMLファイルに分散している可能性
        # まずanalysis.yamlを試す
        try:
            analysis_data = self.load("analysis.yaml")
            if "tasks" in analysis_data and task_name in analysis_data["tasks"]:
                return analysis_data["tasks"][task_name]
        except FileNotFoundError:
            pass

        # script_generation.yamlを試す
        try:
            script_data = self.load("script_generation.yaml")
            if "tasks" in script_data and task_name in script_data["tasks"]:
                return script_data["tasks"][task_name]
        except FileNotFoundError:
            pass

        # quality_check.yamlを試す
        try:
            quality_data = self.load("quality_check.yaml")
            if "tasks" in quality_data and task_name in quality_data["tasks"]:
                return quality_data["tasks"][task_name]
        except FileNotFoundError:
            pass

        raise ValueError(f"Task template '{task_name}' not found in any YAML file")

    def get_script_prompt(self, prompt_type: str = "base") -> str:
        """台本生成プロンプトを取得"""
        script_data = self.load("script_generation.yaml")
        prompts = script_data.get("prompts", {})
        return prompts.get(prompt_type, "")

    def clear_cache(self):
        """キャッシュをクリア"""
        self._cache.clear()


# グローバルインスタンス
_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    """プロンプトマネージャーのシングルトンインスタンスを取得"""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager


def load_prompt_template(filename: str) -> Dict[str, Any]:
    """プロンプトテンプレートを読み込み（簡易関数）"""
    manager = get_prompt_manager()
    return manager.load(filename)


def render_prompt(filename: str, template_name: str, **variables) -> str:
    """プロンプトをレンダリング（簡易関数）"""
    manager = get_prompt_manager()
    return manager.render(filename, template_name, **variables)
