"""
ニュース収集モジュール

Anthropic Claudeを使用して最新の経済ニュースを収集・要約します。
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import httpx
from anthropic import Anthropic
from app.config import cfg

logger = logging.getLogger(__name__)

class NewsCollector:
    """ニュース収集クラス"""

    def __init__(self):
        self.client = None
        self._setup_client()

    def _setup_client(self):
        """Anthropic APIクライアントを初期化"""
        try:
            if not cfg.anthropic_api_key:
                raise ValueError("Anthropic API key not configured")

            self.client = Anthropic(api_key=cfg.anthropic_api_key)
            logger.info("Anthropic client initialized")

        except Exception as e:
            logger.error(f"Failed to initialize Anthropic client: {e}")
            raise

    def collect_news(self, prompt_a: str, mode: str = "daily") -> List[Dict[str, Any]]:
        """
        ニュースを収集・要約

        Args:
            prompt_a: ニュース収集用プロンプト
            mode: 実行モード (daily/special/test)

        Returns:
            ニュース項目のリスト
        """
        try:
            # モードに応じてプロンプトを調整
            adjusted_prompt = self._adjust_prompt_for_mode(prompt_a, mode)

            # Claude APIを呼び出し
            response = self._call_claude_with_retry(adjusted_prompt)

            # 結果をパース
            news_items = self._parse_news_response(response)

            # 検証とクリーニング
            validated_news = self._validate_news_items(news_items)

            logger.info(f"Collected {len(validated_news)} news items (mode: {mode})")
            return validated_news

        except Exception as e:
            logger.error(f"Failed to collect news: {e}")
            return self._get_fallback_news(mode)

    def _adjust_prompt_for_mode(self, base_prompt: str, mode: str) -> str:
        """モードに応じてプロンプトを調整"""
        mode_adjustments = {
            "daily": """
今日（{date}）の経済ニュースを中心に、以下の基準で選択してください：
- 市場への影響度が高い
- 投資家が注目している
- 日本経済との関連性がある
""",
            "special": """
特集記事として、より深掘りした分析を含めてください：
- 背景情報を詳細に
- 専門家の見解を含める
- 将来的な影響を分析
""",
            "test": """
テスト実行のため、簡潔で検証しやすい内容にしてください：
- 項目数は2-3件
- 確実に存在する情報源
- 短時間で処理可能な内容
"""
        }

        adjustment = mode_adjustments.get(mode, "")
        current_date = datetime.now().strftime("%Y年%m月%d日")

        full_prompt = f"""
{base_prompt}

{adjustment.format(date=current_date)}

以下のJSON形式で厳密に回答してください：
```json
[
  {{
    "title": "ニュースのタイトル",
    "url": "https://実在する出典URL",
    "summary": "要約（200-300文字）",
    "key_points": ["重要ポイント1", "重要ポイント2", "重要ポイント3"],
    "source": "情報源名（例：日本経済新聞、Reuters、Bloomberg）",
    "impact_level": "high/medium/low",
    "category": "経済/金融/企業/国際/政策"
  }}
]
```

注意事項：
- 必ず有効なJSONフォーマットで回答
- URLは実在するものを使用
- 信頼性の高いメディアからの情報を優先
- 日付は{current_date}に近い最新情報
"""
        return full_prompt

    def _call_claude_with_retry(self, prompt: str, max_retries: int = 3) -> str:
        """リトライ機能付きClaude API呼び出し"""
        import time
        import random

        for attempt in range(max_retries):
            try:
                response = self.client.messages.create(
                    model="claude-3-sonnet-20240229",
                    max_tokens=4000,
                    temperature=0.3,  # 一貫性を重視
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                )

                content = response.content[0].text
                logger.debug(f"Claude response length: {len(content)}")
                return content

            except Exception as e:
                if "rate_limit" in str(e).lower() and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"Rate limit hit, waiting {wait_time:.2f}s...")
                    time.sleep(wait_time)
                    continue

                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.warning(f"Claude API error, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                    continue

                raise

        raise Exception("Max retries exceeded for Claude API")

    def _parse_news_response(self, response: str) -> List[Dict[str, Any]]:
        """Claude応答からニュースデータを抽出"""
        try:
            # JSON部分を抽出
            start_markers = ["```json", "[", "{"]
            end_markers = ["```", "]", "}"]

            json_start = -1
            json_end = -1

            # 開始位置を探す
            for marker in start_markers:
                pos = response.find(marker)
                if pos != -1:
                    if marker == "```json":
                        json_start = pos + len(marker)
                    elif marker in ["[", "{"]:
                        json_start = pos
                    break

            # 終了位置を探す
            if json_start != -1:
                remaining = response[json_start:]
                for marker in end_markers:
                    if marker == "```":
                        pos = remaining.find(marker)
                    elif marker == "]":
                        pos = remaining.rfind(marker)
                    elif marker == "}":
                        # 最後の}を探す
                        pos = remaining.rfind(marker)

                    if pos != -1:
                        json_end = json_start + pos
                        if marker in ["]", "}"]:
                            json_end += 1
                        break

            if json_start != -1 and json_end != -1:
                json_str = response[json_start:json_end].strip()

                # JSONとして解析
                news_data = json.loads(json_str)

                # リストでない場合はリストに変換
                if isinstance(news_data, dict):
                    news_data = [news_data]

                return news_data

            else:
                logger.warning("No valid JSON found in Claude response")
                return []

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Claude response: {e}")
            logger.debug(f"Raw response: {response[:500]}...")
            return []

    def _validate_news_items(self, news_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """ニュース項目の検証とクリーニング"""
        validated = []

        for item in news_items:
            try:
                # 必須フィールドの確認
                required_fields = ["title", "url", "summary", "source"]
                if not all(field in item and item[field] for field in required_fields):
                    logger.warning(f"Skipping invalid news item: missing required fields")
                    continue

                # URLの基本検証
                url = item.get("url", "")
                if not (url.startswith("http://") or url.startswith("https://")):
                    logger.warning(f"Invalid URL format: {url}")
                    item["url"] = f"https://example.com/news/{hash(item['title']) % 10000}"

                # デフォルト値の設定
                validated_item = {
                    "title": str(item["title"])[:200],  # 長さ制限
                    "url": item["url"],
                    "summary": str(item["summary"])[:500],  # 長さ制限
                    "key_points": item.get("key_points", [])[:5],  # 最大5個
                    "source": str(item["source"]),
                    "impact_level": item.get("impact_level", "medium"),
                    "category": item.get("category", "経済"),
                    "collected_at": datetime.now().isoformat()
                }

                validated.append(validated_item)

            except Exception as e:
                logger.warning(f"Failed to validate news item: {e}")
                continue

        return validated

    def _get_fallback_news(self, mode: str) -> List[Dict[str, Any]]:
        """フォールバック用のダミーニュース"""
        current_time = datetime.now().isoformat()

        fallback_news = [
            {
                "title": f"ニュース収集エラー - {mode}モード",
                "url": "https://example.com/error",
                "summary": f"ニュース収集中にエラーが発生しました。モード: {mode}。手動での確認が必要です。システム管理者に連絡してください。",
                "key_points": [
                    "API接続エラー",
                    "手動確認が必要",
                    "システム管理者への連絡が必要"
                ],
                "source": "システム",
                "impact_level": "high",
                "category": "システム",
                "collected_at": current_time
            }
        ]

        if mode == "test":
            # テストモード用の追加ダミーデータ
            fallback_news.append({
                "title": "テスト用ニュース項目",
                "url": "https://example.com/test",
                "summary": "これはテスト実行用のダミーニュースです。実際の運用では実在のニュースに置き換えられます。",
                "key_points": [
                    "テストデータ",
                    "ダミー情報",
                    "実運用時は削除"
                ],
                "source": "テストシステム",
                "impact_level": "low",
                "category": "テスト",
                "collected_at": current_time
            })

        return fallback_news

    def search_specific_topic(self, topic: str, num_items: int = 3) -> List[Dict[str, Any]]:
        """特定トピックに関するニュースを検索

        Args:
            topic: 検索トピック
            num_items: 取得件数

        Returns:
            ニュース項目のリスト
        """
        prompt = f"""
以下のトピックに関する最新のニュースを{num_items}件収集してください：

トピック: {topic}

以下の基準で選択してください：
- {topic}に直接関連する内容
- 最新の情報（過去1週間以内）
- 信頼性の高い情報源
- 分析価値の高い内容

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

        try:
            response = self._call_claude_with_retry(prompt)
            news_items = self._parse_news_response(response)
            return self._validate_news_items(news_items)

        except Exception as e:
            logger.error(f"Failed to search topic '{topic}': {e}")
            return self._get_fallback_news("special")

# グローバルインスタンス
news_collector = NewsCollector() if cfg.anthropic_api_key else None

def collect_news(prompt_a: str, mode: str = "daily") -> List[Dict[str, Any]]:
    """ニュース収集の簡易関数"""
    if news_collector:
        return news_collector.collect_news(prompt_a, mode)
    else:
        logger.warning("News collector not available, using fallback")
        return NewsCollector()._get_fallback_news(mode)

def search_topic(topic: str, num_items: int = 3) -> List[Dict[str, Any]]:
    """トピック検索の簡易関数"""
    if news_collector:
        return news_collector.search_specific_topic(topic, num_items)
    else:
        logger.warning("News collector not available, using fallback")
        return NewsCollector()._get_fallback_news("special")

if __name__ == "__main__":
    # テスト実行
    print("Testing news collection...")

    # 設定確認
    print(f"Anthropic API configured: {bool(cfg.anthropic_api_key)}")

    if cfg.anthropic_api_key:
        # テストプロンプト
        test_prompt = """
今日の重要な経済ニュースを2-3件収集してください：
- 株式市場の動向
- 企業の決算情報
- 政策関連の発表

信頼性の高い情報源からの最新情報を優先してください。
"""

        # ニュース収集テスト
        try:
            collector = NewsCollector()
            news = collector.collect_news(test_prompt, "test")
            print(f"Collected {len(news)} news items:")

            for i, item in enumerate(news, 1):
                print(f"\n{i}. {item['title']}")
                print(f"   Source: {item['source']}")
                print(f"   Summary: {item['summary'][:100]}...")

        except Exception as e:
            print(f"Test failed: {e}")
    else:
        print("Anthropic API not configured, skipping test")