"""AI APIクライアントの抽象化レイヤー

Gemini、Perplexityなどの異なるAI APIを統一インターフェースで扱う
"""

import logging
import os  # 追加
import random
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import google.generativeai as genai
import httpx

from app.api_rotation import get_rotation_manager  # 追加
from app.config.settings import settings

logger = logging.getLogger(__name__)


class AIClient(ABC):
    """AI APIクライアントの抽象基底クラス"""

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """テキスト生成

        Args:
            prompt: 入力プロンプト
            **kwargs: 追加パラメータ（temperature, max_tokensなど）

        Returns:
            生成されたテキスト
        """
        pass

    @abstractmethod
    def generate_structured(self, prompt: str, schema: Optional[Dict] = None) -> Dict[str, Any]:
        """構造化データ生成（JSON出力）

        Args:
            prompt: 入力プロンプト
            schema: 出力スキーマ（Pydantic互換）

        Returns:
            生成されたデータ（辞書形式）
        """
        pass


class GeminiClient(AIClient):
    """Gemini APIクライアント

    リトライ機能、タイムアウト処理、504エラー対策を含む
    """

    def __init__(
        self,
        model: str = "gemini-2.0-flash-exp",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout_seconds: int = 120,
    ):
        """
        Args:
            model: モデル名
            temperature: 温度パラメータ
            max_tokens: 最大トークン数
            timeout_seconds: タイムアウト（秒）
        """
        self.model_name = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds

        # Rotation managerは main.py で初期化済み
        # キー登録は不要（initialize_api_infrastructure()で実行済み）
        self.rotation_manager = get_rotation_manager()
        self.client = None

        logger.info(f"GeminiClient initialized: model={model}, temp={temperature}")

    def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
        max_retries: int = 3,
    ) -> str:
        """テキスト生成（リトライ機能付き）

        Args:
            prompt: 入力プロンプト
            temperature: 温度（Noneの場合はインスタンスのデフォルト）
            max_tokens: 最大トークン数
            timeout_seconds: タイムアウト
            max_retries: 最大リトライ回数

        Returns:
            生成されたテキスト

        Raises:
            Exception: API呼び出しが失敗した場合
        """
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        timeout = timeout_seconds if timeout_seconds is not None else self.timeout_seconds

        generation_config = genai.GenerationConfig(
            temperature=temp,
            top_p=0.95,
            top_k=40,
            max_output_tokens=tokens,
        )

        rotation_manager = self.rotation_manager

        def api_call_with_key(api_key_value: str) -> str:
            """単一APIキーでの呼び出し"""
            try:
                genai.configure(api_key=api_key_value)
                client = genai.GenerativeModel(f"models/{self.model_name}")

                response = client.generate_content(prompt, generation_config=generation_config, timeout=timeout)
                content = response.text
                logger.debug(f"Generated {len(content)} characters")
                return content
            except Exception as e:
                error_str = str(e).lower()
                if any(kw in error_str for kw in ["429", "rate limit", "quota"]):
                    logger.warning(f"Gemini rate limit detected: {e}")
                    raise  # rotation_managerがハンドリング
                if any(kw in error_str for kw in ["504", "deadline exceeded", "timeout"]):
                    logger.warning(f"Gemini timeout detected: {e}")
                    raise  # rotation_managerがハンドリング
                logger.warning(f"Gemini API error: {e}")
                raise  # rotation_managerがハンドリング

        try:
            return rotation_manager.execute_with_rotation(
                provider="gemini", api_call=api_call_with_key, max_attempts=max_retries
            )
        except Exception as e:
            logger.error(f"All Gemini API attempts failed: {e}")
            raise Exception("Gemini API failed with all keys")

    def generate_structured(self, prompt: str, schema: Optional[Dict] = None) -> Dict[str, Any]:
        """構造化データ生成（JSON出力）

        Args:
            prompt: 入力プロンプト（JSON出力を要求するプロンプト）
            schema: 出力スキーマ（現在は未使用、将来的に型チェックに使用）

        Returns:
            生成されたJSON（辞書形式）
        """
        import json
        import re

        # JSON出力を明示的に要求
        structured_prompt = f"""
{prompt}

【重要】出力は必ず有効なJSON形式で返してください。
```json
{{
  // ここにJSONデータ
}}
```
        """

        response_text = self.generate(structured_prompt)

        # JSON部分を抽出
        try:
            # ```json ... ``` のパターンを探す
            match = re.search(r"```json\n(.*?)\n```", response_text, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                # フォールバック: 最初と最後の{}を探す
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if start != -1 and end != 0:
                    json_str = response_text[start:end]
                else:
                    raise ValueError("No JSON found in response")

            data = json.loads(json_str)
            return data

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse JSON from Gemini response: {e}")
            logger.debug(f"Raw response: {response_text[:500]}...")
            raise ValueError(f"Invalid JSON response from Gemini: {e}")


class PerplexityClient(AIClient):
    """Perplexity APIクライアント

    リトライ機能、タイムアウト処理を含む
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "sonar", timeout_seconds: int = 120):
        self.api_key = api_key or settings.api_keys.get("perplexity") or os.getenv("PERPLEXITY_API_KEY")
        if not self.api_key:
            raise ValueError("Perplexity API key not found. Please set PERPLEXITY_API_KEY or configure in AppSettings.")

        self.model = model
        self.api_url = "https://api.perplexity.ai/chat/completions"
        self.timeout_seconds = timeout_seconds

        logger.info(f"PerplexityClient initialized: model={model}")

    def generate(self, prompt: str, max_retries: int = 3, **kwargs) -> str:
        """テキスト生成（リトライ機能付き）"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert financial news analyst. Provide answers in the requested format.",
                },
                {"role": "user", "content": prompt},
            ],
        }

        for attempt in range(max_retries):
            try:
                logger.debug(f"Perplexity API call (attempt {attempt+1}/{max_retries})")

                with httpx.Client() as client:
                    response = client.post(self.api_url, json=payload, headers=headers, timeout=self.timeout_seconds)
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]

                    logger.debug(f"Generated {len(content)} characters")
                    return content

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    # Rate limit
                    wait_time = (2**attempt) + random.uniform(0, 1)
                    logger.warning(f"Perplexity rate limit, waiting {wait_time:.2f}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Perplexity API error: {e}\nResponse: {e.response.text}")
                    raise

            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.warning(f"Perplexity API error, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                    continue
                raise

        raise Exception(f"Perplexity API: Max retries ({max_retries}) exceeded")

    def generate_structured(self, prompt: str, schema: Optional[Dict] = None) -> Dict[str, Any]:
        """構造化データ生成（JSON出力）"""
        import json
        import re

        # JSON出力を要求
        structured_prompt = f"""
{prompt}

Output your response in valid JSON format.
        """

        response_text = self.generate(structured_prompt)

        # JSON抽出（Geminiと同じロジック）
        try:
            match = re.search(r"```json\n(.*?)\n```", response_text, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                start = response_text.find("[")
                end = response_text.rfind("]") + 1
                if start != -1 and end != 0:
                    json_str = response_text[start:end]
                else:
                    # {} で試す
                    start = response_text.find("{")
                    end = response_text.rfind("}") + 1
                    if start != -1 and end != 0:
                        json_str = response_text[start:end]
                    else:
                        raise ValueError("No JSON found in response")

            data = json.loads(json_str)
            return data

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse JSON from Perplexity response: {e}")
            raise ValueError(f"Invalid JSON response from Perplexity: {e}")


class FallbackAIClient(AIClient):
    """Gemini → Perplexity 自動フォールバック付きクライアント"""

    def __init__(
        self,
        gemini_model: str = "gemini-2.0-flash-exp",
        perplexity_model: str = "sonar",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout_seconds: int = 120,
    ):
        """
        Args:
            gemini_model: Geminiモデル名
            perplexity_model: Perplexityモデル名（フォールバック用）
            temperature: 温度パラメータ
            max_tokens: 最大トークン数
            timeout_seconds: タイムアウト（秒）
        """
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds

        # Primary: Gemini
        try:
            self.primary_client = GeminiClient(
                model=gemini_model, temperature=temperature, max_tokens=max_tokens, timeout_seconds=timeout_seconds
            )
            self.current_client = "gemini"
            logger.info("FallbackAIClient using Gemini as primary")
        except Exception as e:
            logger.warning(f"Gemini initialization failed, starting with Perplexity: {e}")
            self.primary_client = None
            self.current_client = "perplexity"

        # Fallback: Perplexity
        try:
            self.fallback_client = PerplexityClient(model=perplexity_model, timeout_seconds=timeout_seconds)
        except Exception as e:
            logger.error(f"Perplexity initialization also failed: {e}")
            self.fallback_client = None

        if not self.primary_client and not self.fallback_client:
            raise RuntimeError("Both Gemini and Perplexity initialization failed")

    def generate(self, prompt: str, **kwargs) -> str:
        """テキスト生成（自動フォールバック付き）"""
        # Try primary client first
        if self.primary_client and self.current_client == "gemini":
            try:
                return self.primary_client.generate(prompt, **kwargs)
            except Exception as e:
                logger.warning(f"Gemini failed during generation: {e}")
                if self.fallback_client:
                    logger.info("Switching to Perplexity fallback")
                    self.current_client = "perplexity"
                else:
                    raise

        # Use fallback
        if self.fallback_client:
            return self.fallback_client.generate(prompt, **kwargs)
        else:
            raise RuntimeError("No available AI client")

    def generate_structured(self, prompt: str, schema: Optional[Dict] = None) -> Dict[str, Any]:
        """構造化データ生成（自動フォールバック付き）"""
        # Try primary client first
        if self.primary_client and self.current_client == "gemini":
            try:
                return self.primary_client.generate_structured(prompt, schema)
            except Exception as e:
                logger.warning(f"Gemini failed during structured generation: {e}")
                if self.fallback_client:
                    logger.info("Switching to Perplexity fallback")
                    self.current_client = "perplexity"
                else:
                    raise

        # Use fallback
        if self.fallback_client:
            return self.fallback_client.generate_structured(prompt, schema)
        else:
            raise RuntimeError("No available AI client")


class AIClientFactory:
    """AI Clientファクトリー

    クライアントタイプに応じて適切なインスタンスを生成
    """

    @staticmethod
    def create(
        client_type: str, model: Optional[str] = None, temperature: Optional[float] = None, **kwargs
    ) -> AIClient:
        """AI Clientを生成

        Args:
            client_type: "gemini", "perplexity", or "fallback"
            model: モデル名（Noneの場合はデフォルト）
            temperature: 温度パラメータ
            **kwargs: その他のパラメータ

        Returns:
            AI Clientインスタンス

        Raises:
            ValueError: 不明なclient_typeの場合
        """
        if client_type.lower() == "gemini":
            return GeminiClient(model=model, temperature=temperature, **kwargs)
        elif client_type.lower() == "perplexity":
            return PerplexityClient(model=model, **kwargs)
        elif client_type.lower() == "fallback":
            return FallbackAIClient(gemini_model=model, temperature=temperature, **kwargs)
        else:
            raise ValueError(f"Unknown AI client type: {client_type}")

    @staticmethod
    def create_from_agent_config(agent_name: str, use_fallback: bool = True) -> AIClient:
        """エージェント設定からAI Clientを生成（Perplexity自動フォールバック付き）

        Args:
            agent_name: エージェント名（config.yamlに定義）
            use_fallback: True=自動フォールバック有効、False=Geminiのみ

        Returns:
            AI Clientインスタンス
        """
        from app.config_prompts.prompts import get_prompt_manager

        pm = get_prompt_manager()
        agent_config = pm.get_agent_config(agent_name)

        if use_fallback:
            # FallbackAIClientを使用（推奨）
            return FallbackAIClient(
                gemini_model=agent_config.get("model", "gemini-2.0-flash-exp"),
                perplexity_model="sonar",
                temperature=agent_config.get("temperature", 0.7),
                max_tokens=agent_config.get("max_tokens", 4096),
                timeout_seconds=agent_config.get("timeout_seconds", 300),
            )
        else:
            # Geminiのみ（フォールバックなし）
            return GeminiClient(
                model=agent_config.get("model", "gemini-2.0-flash-exp"),
                temperature=agent_config.get("temperature", 0.7),
                max_tokens=agent_config.get("max_tokens", 4096),
                timeout_seconds=agent_config.get("timeout_seconds", 300),
            )


# ===================================
# 便利関数
# ===================================


def get_gemini_client(model: str = "gemini-2.5-flash", temperature: float = 0.7, **kwargs) -> GeminiClient:
    """Gemini Clientを取得（簡易関数）"""
    return GeminiClient(model=model, temperature=temperature, **kwargs)


def get_perplexity_client(model: str = "sonar", **kwargs) -> PerplexityClient:
    """Perplexity Clientを取得（簡易関数）"""
    return PerplexityClient(model=model, **kwargs)


# ===================================
# CrewAI用LangChainラッパー
# ===================================

try:
    import google.generativeai as genai_sdk
    from langchain_core.language_models.llms import LLM as BaseLLM

    class GeminiDirectLLM(BaseLLM):
        """Direct Gemini SDK LLM - bypasses ALL LiteLLM/Vertex AI routing"""

        model_name: str = "gemini-2.0-flash-exp"
        temperature: float = 0.7
        api_key: str = ""
        _genai_client: Any = None

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            # Configure Gemini SDK directly
            genai_sdk.configure(api_key=self.api_key)
            self._genai_client = genai_sdk.GenerativeModel(f"models/{self.model_name}")
            logger.info(f"Initialized GeminiDirectLLM with model: {self.model_name}")

        @property
        def _llm_type(self) -> str:
            return "gemini-direct"

        def _call(self, prompt: str, stop: Optional[List[str]] = None, **kwargs: Any) -> str:
            try:
                config = genai_sdk.GenerationConfig(
                    temperature=self.temperature,
                    top_p=0.95,
                    top_k=40,
                    max_output_tokens=4096,
                )
                response = self._genai_client.generate_content(prompt, generation_config=config)
                return response.text
            except Exception as e:
                logger.error(f"Gemini Direct call failed: {e}")
                raise

    def get_crewai_gemini_llm(model: str = "gemini-pro", temperature: float = 0.7, **kwargs):
        """CrewAI用のGemini LLM（Direct SDK - NO LiteLLM/Vertex AI）"""
        # モデル名の正規化 - Google AI Studio API compatible names
        model_mapping = {
            "gemini-2.0-flash-exp": "gemini-2.0-flash-exp",
            "gemini-pro": "gemini-1.5-pro-latest",
            "gemini-1.5-pro": "gemini-1.5-pro-latest",
            "gemini-1.5-flash": "gemini-1.5-flash-latest",
        }

        clean_model = model.replace("models/", "") if model.startswith("models/") else model
        final_model = model_mapping.get(clean_model, clean_model)

        logger.info(f"CrewAI LLM: {model} -> {final_model} (Direct Gemini SDK)")

        return GeminiDirectLLM(
            model=final_model,  # model_nameをmodelに変更
            temperature=temperature,
            # api_keyはGeminiClient内でrotation_managerから取得するため不要
        )

except ImportError as e:
    logger.warning(f"Failed to import required modules for CrewAI: {e}")

    def get_crewai_gemini_llm(model: str = "gemini-pro", temperature: float = 0.7, **kwargs):
        """Fallback: GeminiClientを返す"""
        logger.warning("Using fallback GeminiClient instead of LangChain wrapper")
        return get_gemini_client(model=model, temperature=temperature, **kwargs)
