"""ニュース収集モジュール
Perplexity AIを使用して最新の経済ニュースを収集・要約します。
"""
import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, Tuple
import httpx
from .api_rotation import get_rotation_manager
from .config import cfg
from .llm_logging import llm_logging_context, record_llm_interaction
from app.prompts import build_news_collection_prompt, get_news_collection_system_message
logger = logging.getLogger(__name__)
class PerplexityKeyProvider(Protocol):
    """Perplexity APIキーの供給インターフェース"""
    def get_keys(self) -> List[Tuple[str, str]]:
        """(key_name, key_value) のリストを返す"""
class ConfigAndEnvPerplexityKeyProvider:
    """設定と環境変数の両方からPerplexityキーを提供する"""
    def __init__(self, config_key: Optional[str], env: Optional[dict[str, str]] = None):
        self._config_key = config_key
        self._env = env or os.environ
    def get_keys(self) -> List[Tuple[str, str]]:
        keys: List[Tuple[str, str]] = []
        seen_values: set[str] = set()
        if self._config_key:
            keys.append(("config.api_keys.perplexity", self._config_key))
            seen_values.add(self._config_key)
        for i in range(1, 10):
            key_name = f"PERPLEXITY_API_KEY_{i}" if i > 1 else "PERPLEXITY_API_KEY"
            key_value = self._env.get(key_name)
            if key_value and key_value not in seen_values:
                keys.append((key_name, key_value))
                seen_values.add(key_value)
        return keys
class StaticPerplexityKeyProvider:
    """テスト用などで固定キーを提供する"""
    def __init__(self, keys: Optional[List[Tuple[str, str]]] = None):
        self._keys = list(keys or [])
    def get_keys(self) -> List[Tuple[str, str]]:
        return list(self._keys)
class NewsCollector:
    """ニュース収集クラス"""
    def __init__(
        self,
        key_provider: Optional[PerplexityKeyProvider] = None,
    ):
        self.api_url = "https://api.perplexity.ai/chat/completions"
        self.newsapi_url = "https://newsapi.org/v2/everything"
        self._rotation_manager = get_rotation_manager()
        self._key_provider = key_provider or ConfigAndEnvPerplexityKeyProvider(cfg.perplexity_api_key)
        self._has_registered_keys = self._register_perplexity_keys()
        logger.info("NewsCollector initialized with key rotation and NewsAPI fallback")
    def _register_perplexity_keys(self) -> bool:
        keys = self._key_provider.get_keys() if self._key_provider else []
        if keys:
            self._rotation_manager.register_keys("perplexity", keys)
            logger.info(f"Registered {len(keys)} Perplexity API keys for rotation")
            return True
        logger.warning("No Perplexity API keys configured")
        return False
    @property
    def has_perplexity_keys(self) -> bool:
        return self._has_registered_keys
    def collect_news(self, prompt_a: str, mode: str = "daily") -> List[Dict[str, Any]]:
        """ニュースを収集・要約"""
        try:
            with llm_logging_context(component="news_collection", mode=mode):
                adjusted_prompt = self._adjust_prompt_for_mode(prompt_a, mode)
                if self._has_registered_keys:
                    try:
                        response_text = self._call_perplexity_with_rotation(adjusted_prompt)
                        news_items = self._parse_news_response(response_text)
                        validated_news = self._validate_news_items(news_items)
                        if validated_news:
                            logger.info(
                                f"Collected {len(validated_news)} news items via Perplexity (mode: {mode})"
                            )
                            return validated_news
                    except Exception as e:
                        logger.warning(f"Perplexity collection failed: {e}, trying NewsAPI fallback...")
                else:
                    logger.info("Skipping Perplexity news collection because no API keys were registered")
            if cfg.newsapi_key:
                try:
                    news_items = self._collect_from_newsapi(mode)
                    if news_items:
                        logger.info(f"Collected {len(news_items)} news items via NewsAPI fallback")
                        return news_items
                except Exception as e:
                    logger.warning(f"NewsAPI fallback failed: {e}")
            logger.error("All news collection methods failed")
            return self._get_fallback_news(mode)
        except Exception as e:
            logger.error(f"Failed to collect news: {e}")
            return self._get_fallback_news(mode)
    def _adjust_prompt_for_mode(self, base_prompt: str, mode: str) -> str:
        """モードに応じてプロンプトを調整"""
        return build_news_collection_prompt(base_prompt, mode)
    def _call_perplexity_with_rotation(self, prompt: str, max_attempts: int = 3) -> str:
        """キーローテーション対応Perplexity API呼び出し"""
        def api_call_with_key(api_key: str) -> str:
            """単一APIキーでの呼び出し"""
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "sonar",
                "messages": [
                    {
                        "role": "system",
                        "content": get_news_collection_system_message(),
                    },
                    {"role": "user", "content": prompt},
                ],
            }
            try:
                with httpx.Client() as client:
                    response = client.post(self.api_url, json=payload, headers=headers, timeout=120.0)
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    logger.debug(f"Perplexity response length: {len(content)}")
                    try:
                        record_llm_interaction(
                            provider="perplexity",
                            model=payload.get("model"),
                            prompt=payload["messages"],
                            response={
                                "text": content,
                                "raw": data,
                            },
                            metadata={"component": "news_collection"},
                        )
                    except Exception:
                        logger.debug("Failed to log Perplexity interaction", exc_info=True)
                    return content
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    logger.warning(f"Perplexity rate limit: {e}")
                    raise
                logger.error(f"Perplexity API HTTP error: {e}")
                raise
            except Exception as e:
                logger.warning(f"Perplexity API error: {e}")
                raise
        try:
            return self._rotation_manager.execute_with_rotation(
                provider="perplexity", api_call=api_call_with_key, max_attempts=max_attempts
            )
        except Exception as e:
            logger.error(f"All Perplexity API attempts failed: {e}")
            raise
    def _parse_news_response(self, response: str) -> List[Dict[str, Any]]:
        """Perplexity応答からニュースデータを抽出"""
        try:
            match = re.search(r"```json\n(.*?)\n```", response, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                start = response.find("[")
                end = response.rfind("]") + 1
                if start != -1 and end != 0:
                    json_str = response[start:end]
                else:
                    raise ValueError("No JSON block found in response")
            news_data = json.loads(json_str)
            if isinstance(news_data, dict):
                news_data = [news_data]
            return news_data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Perplexity response: {e}")
            logger.debug(f"Raw response: {response[:500]}...")
            return []
    def _validate_news_items(self, news_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """ニュース項目の検証とクリーニング"""
        validated = []
        for item in news_items:
            try:
                required_fields = ["title", "url", "summary", "source"]
                if not all(field in item and item[field] for field in required_fields):
                    logger.warning("Skipping invalid news item: missing required fields")
                    continue
                item.setdefault("timestamp", datetime.utcnow().isoformat())
                item.setdefault("category", "general")
                if "key_points" in item and isinstance(item["key_points"], list):
                    item["key_points"] = [str(point) for point in item["key_points"]]
                validated.append(item)
            except Exception as e:
                logger.warning(f"Skipping malformed news item: {e}")
        return validated
    def _collect_from_newsapi(self, mode: str) -> List[Dict[str, Any]]:
        """NewsAPIフォールバック処理"""
        params = {
            "q": "economy OR finance OR stock market",
            "language": "ja",
            "pageSize": 5 if mode == "daily" else 3,
            "sortBy": "publishedAt",
            "apiKey": cfg.newsapi_key,
        }
        response = httpx.get(self.newsapi_url, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        articles = data.get("articles", [])
        news_items = []
        for article in articles:
            news_items.append(
                {
                    "title": article.get("title", ""),
                    "url": article.get("url", ""),
                    "summary": article.get("description", ""),
                    "source": article.get("source", {}).get("name", "NewsAPI"),
                    "timestamp": article.get("publishedAt", datetime.utcnow().isoformat()),
                    "category": "general",
                }
            )
        return news_items
    def _call_perplexity_with_retry(self, prompt: str, max_attempts: int = 3) -> str:
        last_error = None
        for attempt in range(max_attempts):
            try:
                return self._call_perplexity_with_rotation(prompt)
            except Exception as e:
                last_error = e
                logger.warning(f"Perplexity attempt {attempt + 1}/{max_attempts} failed: {e}")
        if last_error:
            raise last_error
        raise RuntimeError("Perplexity request failed without specific error")
    def _get_fallback_news(self, mode: str) -> List[Dict[str, Any]]:
        """フォールバックニュース"""
        now = datetime.utcnow()
        return [
            {
                "title": "経済インサイト: 今週の注目トピック",
                "url": "https://example.com/economy-insights",
                "summary": "市場動向と政策発表の主要ポイントをまとめました。",
                "source": "Fallback",
                "timestamp": now.isoformat(),
                "category": "general",
                "key_points": [
                    "株式市場のボラティリティ上昇",
                    "中央銀行による金融政策の示唆",
                    "主要企業の決算発表",
                ],
            },
        ]
    def search_specific_topic(self, topic: str, num_items: int = 3) -> List[Dict[str, Any]]:
        """特定トピックに関するニュースを検索"""
        prompt = f"""
以下のトピックに関する最新のニュースを{num_items}件収集してください：
トピック: {topic}
JSON形式で回答してください：
[
  {{
    "title": "...",
    "url": "...",
    "summary": "...",
    "key_points": [...],
    "source": "...",
    "impact_level": "...",
    "category": "..."
  }}
]
"""
        if not self._has_registered_keys:
            logger.info("Skipping Perplexity topic search because no API keys were registered")
            return self._get_fallback_news("special")
        try:
            response = self._call_perplexity_with_retry(prompt)
            news_items = self._parse_news_response(response)
            return self._validate_news_items(news_items)
        except Exception as e:
            logger.error(f"Failed to search topic '{topic}': {e}")
            return self._get_fallback_news("special")
def create_news_collector(key_provider: Optional[PerplexityKeyProvider] = None) -> Optional[NewsCollector]:
    """ニュースコレクターを生成するファクトリ"""
    provider = key_provider or ConfigAndEnvPerplexityKeyProvider(cfg.perplexity_api_key)
    keys = provider.get_keys()
    if not keys:
        logger.warning("No Perplexity API keys available; NewsCollector remains disabled")
        return None
    collector = NewsCollector(key_provider=StaticPerplexityKeyProvider(keys))
    if not collector.has_perplexity_keys:
        return None
    return collector
def _fallback_news(mode: str) -> List[Dict[str, Any]]:
    return NewsCollector(StaticPerplexityKeyProvider())._get_fallback_news(mode)
news_collector = create_news_collector()
def collect_news(prompt_a: str, mode: str = "daily") -> List[Dict[str, Any]]:
    """ニュース収集の簡易関数"""
    if news_collector:
        return news_collector.collect_news(prompt_a, mode)
    logger.warning("News collector not available, using fallback")
    return _fallback_news(mode)
def search_topic(topic: str, num_items: int = 3) -> List[Dict[str, Any]]:
    """トピック検索の簡易関数"""
    if news_collector:
        return news_collector.search_specific_topic(topic, num_items)
    logger.warning("News collector not available, using fallback")
    return _fallback_news("special")
if __name__ == "__main__":
    print("Testing news collection...")
    if news_collector:
        test_prompt = """
今日の重要な経済ニュースを2-3件収集してください：
- 株式市場の動向
- 企業の決算情報
- 政策関連の発表
信頼性の高い情報源からの最新情報を優先してください。
"""
        try:
            news = news_collector.collect_news(test_prompt, "test")
            print(f"Collected {len(news)} news items:")
            for i, item in enumerate(news, 1):
                print(f"\n{i}. {item['title']}")
                print(f"   Source: {item['source']}")
                print(f"   Summary: {item['summary'][:100]}...")
        except Exception as e:
            print(f"Test failed: {e}")
    else:
        print("Perplexity API not configured, skipping test")
