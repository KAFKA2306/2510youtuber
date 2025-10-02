"""AI APIクライアントの抽象化レイヤー

Gemini、Perplexityなどの異なるAI APIを統一インターフェースで扱う
"""

import logging
import os # 追加
import random
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

import google.generativeai as genai
import httpx

from app.config import cfg as settings

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
        api_key: Optional[str] = None,
        model: str = "gemini-2.5-flash",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout_seconds: int = 120
    ):
        """
        Args:
            api_key: Gemini API Key（Noneの場合は設定から取得）
            model: モデル名
            temperature: 温度パラメータ
            max_tokens: 最大トークン数
            timeout_seconds: タイムアウト（秒）
        """
        self.api_key = api_key or settings.gemini_api_key
        if not self.api_key:
            raise ValueError("Gemini API key not found")

        self.model_name = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds

        # GOOGLE_APPLICATION_CREDENTIALS が設定されているとVertex AIが優先されるため、一時的に無効化
        original_google_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if original_google_creds:
            del os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
            logger.debug("Temporarily unset GOOGLE_APPLICATION_CREDENTIALS to prevent Vertex AI preference.")

        # LiteLLMがVertex AIをプロバイダーとして認識しないように環境変数をクリア
        if "LITELLM_GEMINI_PROJECT" in os.environ:
            del os.environ["LITELLM_GEMINI_PROJECT"]
            logger.debug("Cleared LITELLM_GEMINI_PROJECT.")
        if "LITELLM_GEMINI_LOCATION" in os.environ:
            del os.environ["LITELLM_GEMINI_LOCATION"]
            logger.debug("Cleared LITELLM_GEMINI_LOCATION.")

        # LiteLLMがGoogle AI Studio APIを使用するように環境変数を設定
        os.environ["LITELLM_MODEL"] = f"gemini/{model}" # モデル名を直接指定
        os.environ["LITELLM_API_KEY"] = self.api_key
        os.environ["LITELLM_API_BASE"] = "https://generativelanguage.googleapis.com/v1beta"
        logger.debug(f"Set LiteLLM environment variables: LITELLM_MODEL={os.environ['LITELLM_MODEL']}, LITELLM_API_BASE={os.environ['LITELLM_API_BASE']}")

        try:
            # Gemini APIクライアントを初期化
            genai.configure(api_key=self.api_key)
            self.client = genai.GenerativeModel(f"models/{model}")
        finally:
            # 環境変数を元に戻す
            if original_google_creds:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = original_google_creds
                logger.debug("Restored GOOGLE_APPLICATION_CREDENTIALS.")
            # LiteLLMの環境変数もクリーンアップ
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
            logger.debug("Cleaned up LiteLLM environment variables.")

        logger.info(f"GeminiClient initialized: model={model}, temp={temperature}")

    def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
        max_retries: int = 3
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

        for attempt in range(max_retries):
            try:
                logger.debug(f"Gemini API call (attempt {attempt+1}/{max_retries})")

                # Note: request_options is not supported in this version of google-generativeai
                # タイムアウトはhttpxレベルで管理
                response = self.client.generate_content(
                    prompt,
                    generation_config=generation_config
                )

                content = response.text
                logger.debug(f"Generated {len(content)} characters")
                return content

            except Exception as e:
                error_str = str(e).lower()

                # 504 Deadline Exceeded エラーの特別処理
                if "504" in error_str or "deadline exceeded" in error_str or "timeout" in error_str:
                    if attempt < max_retries - 1:
                        wait_time = 5 + (attempt * 3)
                        logger.warning(f"API timeout (504), retrying in {wait_time}s (attempt {attempt+1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error("API timeout after all retries")
                        raise Exception("Gemini API timeout after all retries")

                # Rate limit エラー処理
                if "rate_limit" in error_str or "429" in error_str:
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) + random.uniform(0, 1)
                        logger.warning(f"Rate limit hit, waiting {wait_time:.2f}s...")
                        time.sleep(wait_time)
                        continue

                # その他のエラー
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 3
                    logger.warning(f"Gemini API error, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                    continue

                # 最大リトライ回数到達
                logger.error(f"Gemini API failed after {max_retries} attempts: {e}")
                raise

        raise Exception(f"Gemini API: Max retries ({max_retries}) exceeded")

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
            match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                # フォールバック: 最初と最後の{}を探す
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
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

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "sonar",
        timeout_seconds: int = 120
    ):
        self.api_key = api_key or settings.perplexity_api_key
        if not self.api_key:
            raise ValueError("Perplexity API key not found")

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
                    response = client.post(
                        self.api_url,
                        json=payload,
                        headers=headers,
                        timeout=self.timeout_seconds
                    )
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]

                    logger.debug(f"Generated {len(content)} characters")
                    return content

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    # Rate limit
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
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
            match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                start = response_text.find('[')
                end = response_text.rfind(']') + 1
                if start != -1 and end != 0:
                    json_str = response_text[start:end]
                else:
                    # {} で試す
                    start = response_text.find('{')
                    end = response_text.rfind('}') + 1
                    if start != -1 and end != 0:
                        json_str = response_text[start:end]
                    else:
                        raise ValueError("No JSON found in response")

            data = json.loads(json_str)
            return data

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse JSON from Perplexity response: {e}")
            raise ValueError(f"Invalid JSON response from Perplexity: {e}")


class AIClientFactory:
    """AI Clientファクトリー

    クライアントタイプに応じて適切なインスタンスを生成
    """

    @staticmethod
    def create(
        client_type: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> AIClient:
        """AI Clientを生成

        Args:
            client_type: "gemini" or "perplexity"
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
        else:
            raise ValueError(f"Unknown AI client type: {client_type}")

    @staticmethod
    def create_from_agent_config(agent_name: str) -> AIClient:
        """エージェント設定からAI Clientを生成

        Args:
            agent_name: エージェント名（config.yamlに定義）

        Returns:
            AI Clientインスタンス
        """
        from app.config_prompts.prompts import get_prompt_manager
        pm = get_prompt_manager()
        agent_config = pm.get_agent_config(agent_name)

        # LiteLLMがVertex AIをプロバイダーとして認識しないように環境変数をクリア
        if "LITELLM_GEMINI_PROJECT" in os.environ:
            del os.environ["LITELLM_GEMINI_PROJECT"]
            logger.debug("Cleared LITELLM_GEMINI_PROJECT.")
        if "LITELLM_GEMINI_LOCATION" in os.environ:
            del os.environ["LITELLM_GEMINI_LOCATION"]
            logger.debug("Cleared LITELLM_GEMINI_LOCATION.")

        # LiteLLMがGoogle AI Studio APIを使用するように環境変数を設定
        os.environ["LITELLM_MODEL"] = f"gemini/{agent_config.get('model', 'gemini-2.0-flash-exp')}" # モデル名を直接指定
        os.environ["LITELLM_API_KEY"] = settings.gemini_api_key
        os.environ["LITELLM_API_BASE"] = "https://generativelanguage.googleapis.com/v1beta"
        logger.debug(f"Set LiteLLM environment variables: LITELLM_MODEL={os.environ['LITELLM_MODEL']}, LITELLM_API_BASE={os.environ['LITELLM_API_BASE']}")

        try:
            # GeminiClientの初期化を試みる
            return GeminiClient(
                model=agent_config.get('model', 'gemini-2.0-flash-exp'),
                temperature=agent_config.get('temperature', 0.7),
                max_tokens=agent_config.get('max_tokens', 4096),
                timeout_seconds=agent_config.get('timeout_seconds', 300)
            )
        except Exception as e:
            error_message = str(e).lower()
            # LiteLLMの環境変数をクリーンアップ
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
            logger.debug("Cleaned up LiteLLM environment variables before fallback.")

            # 課金エラーまたは権限エラーの場合、Perplexityにフォールバック
            if "billing_disabled" in error_message or "403 forbidden" in error_message or "permission_denied" in error_message:
                logger.warning(f"Gemini API billing disabled or forbidden for '{agent_name}'. Falling back to Perplexity API. Error: {e}")
                try:
                    # PerplexityClientの初期化を試みる
                    return PerplexityClient(
                        model=agent_config.get('model', 'sonar-online-7b'), # Perplexityのデフォルトモデル
                        timeout_seconds=agent_config.get('timeout_seconds', 300)
                    )
                except Exception as perplexity_e:
                    logger.error(f"Failed to initialize PerplexityClient as fallback for '{agent_name}': {perplexity_e}")
                    raise RuntimeError(f"Failed to initialize any AI client for '{agent_name}' after Gemini billing error.") from perplexity_e
            else:
                # その他のエラーの場合は、デフォルトのGeminiClientを試す（GeminiClientの__init__でエラーになる可能性もあるため）
                logger.warning(f"Could not initialize GeminiClient for '{agent_name}' due to unexpected error: {e}. Attempting with default GeminiClient.")
                return GeminiClient()
        finally:
            # 処理が完了したらLiteLLMの環境変数をクリーンアップ
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
            logger.debug("Cleaned up LiteLLM environment variables after AIClientFactory.create_from_agent_config.")


# ===================================
# 便利関数
# ===================================

def get_gemini_client(
    model: str = "gemini-2.5-flash",
    temperature: float = 0.7,
    **kwargs
) -> GeminiClient:
    """Gemini Clientを取得（簡易関数）"""
    return GeminiClient(model=model, temperature=temperature, **kwargs)


def get_perplexity_client(model: str = "sonar", **kwargs) -> PerplexityClient:
    """Perplexity Clientを取得（簡易関数）"""
    return PerplexityClient(model=model, **kwargs)


# ===================================
# CrewAI用LangChainラッパー
# ===================================

try:
    from langchain_google_genai import ChatGoogleGenerativeAI

    def get_crewai_gemini_llm(
        model: str = "gemini-pro",
        temperature: float = 0.7,
        **kwargs
    ):
        """CrewAI用のGemini LLM（Google AI Studio経由・無料枠対応）

        Vertex AIではなくGoogle AI Studio APIを使用するため課金不要
        """
        api_key = settings.gemini_api_key
        # LiteLLMがVertex AIではなくGoogle AI Studio APIを使用するように環境変数を設定
        os.environ["LITELLM_GEMINI_API_BASE"] = "https://generativelanguage.googleapis.com/v1beta"
        os.environ["LITELLM_GEMINI_API_KEY"] = api_key
        
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=temperature,
            convert_system_message_to_human=True,
            client_options={"api_endpoint": "generativelanguage.googleapis.com"}, # Vertex AIではなくGoogle AI Studio APIを明示的に使用
            **kwargs
        )
except ImportError:
    logger.warning("langchain_google_genai not installed. CrewAI Gemini LLM unavailable.")

    def get_crewai_gemini_llm(model: str = "gemini-pro", temperature: float = 0.7, **kwargs):
        """Fallback: GeminiClientを返す"""
        logger.warning("Using fallback GeminiClient instead of LangChain wrapper")
        return get_gemini_client(model=model, temperature=temperature, **kwargs)