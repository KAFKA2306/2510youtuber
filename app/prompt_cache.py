import os

import yaml


class PromptManager:
    def __init__(self, prompts_dir="app/config_prompts/prompts"):
        self.prompts_dir = prompts_dir
        self.cache = {}

    def load(self, filename: str) -> dict:
        """YAMLファイルからプロンプト設定をロード"""
        if filename not in self.cache:
            filepath = os.path.join(self.prompts_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    self.cache[filename] = yaml.safe_load(f)
            except FileNotFoundError:
                print(f"Warning: Prompt file not found: {filepath}")
                self.cache[filename] = {}  # ファイルが見つからない場合は空の辞書をキャッシュ
        return self.cache[filename]

    def get_agent_config(self, agent_name: str) -> dict:
        """エージェント設定を取得"""
        agents_data = self.load("agents.yaml")
        return agents_data.get("agents", {}).get(agent_name, {})

    def load_prompts_from_cache(self, mode: str) -> dict:
        """キャッシュからプロンプトをロード"""
        cache_file = os.path.join(self.prompts_dir, f"cache_{mode}.yaml")
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}

    def save_prompts_to_cache(self, mode: str, prompts: dict):
        """プロンプトをキャッシュに保存"""
        cache_file = os.path.join(self.prompts_dir, f"cache_{mode}.yaml")
        with open(cache_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(prompts, f, allow_unicode=True)


def get_prompt_manager():
    return PromptManager()
