# app/crew/tools/ai_clients.py
import logging
from typing import Any, Dict, Optional
import httpx
import google.generativeai as genai

logger = logging.getLogger(__name__)

# 生成時に許可するパラメータ
_ALLOWED_GEN_ARGS = {
    "temperature",
    "top_p",
    "top_k",
    "max_output_tokens",
    "candidate_count",
    "stop_sequences",
    "safety_settings",
}

class GeminiClient:
    """Google Gemini APIクライアント（生成パラメータを__init__で受け、generate時にマージ）"""

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash", **kwargs):
        self.api_key = api_key
        self.model = model
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(model)

        # __init__で受けた温度などを既定configとして保持
        self.default_generation_config: Dict[str, Any] = {}
        for k, v in kwargs.items():
            if k in _ALLOWED_GEN_ARGS and v is not None:
                self.default_generation_config[k] = v

    def generate(self, prompt: str, generation_config: Optional[Dict[str, Any]] = None) -> str:
        try:
            # 既定＋呼び出し時指定をマージ（呼び出し時が優先）
            merged_cfg = dict(self.default_generation_config)
            if generation_config:
                merged_cfg.update({k: v for k, v in generation_config.items() if v is not None})

            # ❌ timeoutは指定しない（SDK仕様変更対策）
            resp = self.client.generate_content(prompt, generation_config=merged_cfg or None)
            return resp.text
        except Exception as e:
            logger.error(f"GeminiClient error: {e}")
            raise

class PerplexityClient:
    """Perplexity APIクライアント（ニュース収集など）"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.perplexity.ai/chat/completions"

    def search(self, query: str) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "sonar-medium-online",
            "messages": [{"role": "user", "content": query}],
        }
        try:
            with httpx.Client(timeout=30) as c:
                r = c.post(self.base_url, headers=headers, json=payload)
                r.raise_for_status()
                data = r.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Perplexity search error: {e}")
            raise

# --- 後方互換レイヤー（既存コードが参照） ---
class AIClient:
    """旧AIClient互換ラッパー（内部はGeminiClient）"""
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash", **kwargs):
        self._client = GeminiClient(api_key=api_key, model=model, **kwargs)
    def generate(self, prompt: str, generation_config: Optional[Dict[str, Any]] = None) -> str:
        return self._client.generate(prompt, generation_config=generation_config)

class AIClientFactory:
    """
    旧コード互換のファクトリー。
    例:
      AIClientFactory.create("gemini", key, model="gemini-1.5-pro", temperature=0.7)
      AIClientFactory.create("perplexity", key)
    """
    @staticmethod
    def create(client_type: str, api_key: str, model: str = "gemini-1.5-flash", **kwargs):
        t = (client_type or "gemini").lower()
        if t == "gemini":
            return GeminiClient(api_key=api_key, model=model, **kwargs)
        if t == "perplexity":
            return PerplexityClient(api_key=api_key)
        raise ValueError(f"Unsupported AI client type: {client_type}")

    # 互換エイリアス
    @staticmethod
    def get(client_type: str, api_key: str, model: str = "gemini-1.5-flash", **kwargs):
        return AIClientFactory.create(client_type, api_key, model, **kwargs)
    @staticmethod
    def build(client_type: str, api_key: str, model: str = "gemini-1.5-flash", **kwargs):
        return AIClientFactory.create(client_type, api_key, model, **kwargs)
    @staticmethod
    def from_env(client_type: str, api_key: str, model: str = "gemini-1.5-flash", **kwargs):
        return AIClientFactory.create(client_type, api_key, model, **kwargs)