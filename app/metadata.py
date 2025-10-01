""" ""
メタデータ生成モジュール

YouTube動画のタイトル、説明文、タグ、カテゴリを自動生成します。
SEO最適化と視聴者エンゲージメント向上を目的とした高品質なメタデータを作成します。
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List

import google.generativeai as genai

from config import cfg

logger = logging.getLogger(__name__)


class MetadataGenerator:
    """メタデータ生成クラス"""

    def __init__(self):
        self.client = None
        self._setup_client()

    def _setup_client(self):
        """Gemini APIクライアントを初期化"""
        try:
            if not cfg.gemini_api_key:
                raise ValueError("Gemini API key not configured")

            genai.configure(api_key=cfg.gemini_api_key)
            self.client = genai.GenerativeModel("gemini-1.5-flash-latest")
            logger.info("Metadata generator initialized with Gemini")

        except Exception as e:
            logger.error(f"Failed to initialize metadata generator: {e}")
            raise

    def generate_youtube_metadata(
        self, news_items: List[Dict[str, Any]], script_content: str = "", mode: str = "daily"
    ) -> Dict[str, Any]:
        """YouTube動画用メタデータを生成"""
        try:
            prompt = self._build_metadata_prompt(news_items, script_content, mode)
            response = self._call_gemini_for_metadata(prompt)
            metadata = self._parse_metadata_response(response)
            validated_metadata = self._validate_metadata(metadata, news_items)
            logger.info(f"Generated metadata for {mode} video")
            return validated_metadata
        except Exception as e:
            logger.error(f"Failed to generate metadata: {e}")
            return self._get_fallback_metadata(news_items, mode)

    def _build_metadata_prompt(self, news_items: List[Dict[str, Any]], script_content: str, mode: str) -> str:
        """メタデータ生成用プロンプトを構築"""
        current_date = datetime.now().strftime("%Y年%m月%d日")
        news_summary = self._create_news_summary(news_items)
        mode_context = {
            "daily": "日次の経済ニュース解説動画",
            "special": "特集・深堀り解説動画",
            "breaking": "速報・緊急ニュース動画",
        }
        prompt = f"""
以下の経済ニュース内容から、YouTube動画用のメタデータを生成してください。

【動画タイプ】{mode_context.get(mode, "経済ニュース解説動画")}
【配信日】{current_date}

【ニュース内容】
{news_summary}

【台本抜粋】
{script_content[:500] if script_content else "台本データなし"}...

【要件】
1. タイトル: 50文字以内、クリック率向上を意識
2. 説明文: 1000-3000文字、SEO最適化
3. タグ: 15-20個、検索性向上
4. カテゴリ: YouTube標準カテゴリ
5. サムネイル文言: 大きく表示するテキスト

【重要な方針】
- 正確性と信頼性を最優先
- 煽りすぎない、品格を保つ
- 検索されやすいキーワードを含める
- 視聴者価値を明確に示す
- 時事性を強調

以下のJSON形式で厳密に回答してください：
```json
{{
  "title": "動画タイトル（50文字以内）",
  "description": "動画説明文（改行を\\nで表現）",
  "tags": ["タグ1", "タグ2", "タグ3", ...],
  "category": "YouTube カテゴリ",
  "thumbnail_text": "サムネイル用テキスト",
  "seo_keywords": ["SEOキーワード1", "SEOキーワード2", ...],
  "target_audience": "ターゲット視聴者層",
  "estimated_watch_time": "推定視聴時間（分）"
}}
```

注意事項：
- 必ず有効なJSONフォーマットで回答
- タイトルは魅力的だが誇張しない
- 説明文には出典情報を含める
- タグは具体的で検索性の高いものを選択
"""
        return prompt

    def _create_news_summary(self, news_items: List[Dict[str, Any]]) -> str:
        """ニュース項目から要約を作成"""
        if not news_items:
            return "ニュースデータが取得できませんでした。"
        summaries = []
        for i, item in enumerate(news_items, 1):
            summary = f"""
【ニュース{i}】{item.get("title", "無題")}
出典: {item.get("source", "不明")}
要約: {item.get("summary", "")[:200]}...
影響度: {item.get("impact_level", "medium")}
"""
            summaries.append(summary)
        return "\n".join(summaries)

    def _call_gemini_for_metadata(self, prompt: str, max_retries: int = 3) -> str:
        """メタデータ生成用Gemini API呼び出し"""
        import random
        import time

        for attempt in range(max_retries):
            try:
                response = self.client.generate_content(prompt)
                content = response.text
                logger.debug(f"Generated metadata response length: {len(content)}")
                return content
            except Exception as e:
                if "rate_limit" in str(e).lower() and attempt < max_retries - 1:
                    wait_time = (2**attempt) + random.uniform(0, 1)
                    logger.warning(f"Rate limit hit, waiting {wait_time:.2f}s...")
                    time.sleep(wait_time)
                    continue
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.warning(f"Metadata generation error, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                    continue
                raise
        raise Exception("Max retries exceeded for metadata generation")

    def _parse_metadata_response(self, response: str) -> Dict[str, Any]:
        """メタデータレスポンスを解析"""
        try:
            match = re.search(r"```json\n(.*?)\n```", response, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                start = response.find("{")
                end = response.rfind("}")
                if start != -1 and end != -1:
                    json_str = response[start : end + 1]
                else:
                    raise ValueError("No JSON structure found")
            metadata = json.loads(json_str)
            return metadata
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse metadata JSON: {e}")
            logger.debug(f"Raw response: {response[:500]}...")
            return {}
        except Exception as e:
            logger.error(f"Error parsing metadata response: {e}")
            return {}

    def _validate_metadata(self, metadata: Dict[str, Any], news_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """メタデータの検証とクリーニング"""
        validated = {}
        try:
            title = str(metadata.get("title", "")).strip()
            if len(title) > 50:
                title = title[:47] + "..."
            validated["title"] = title or self._generate_fallback_title(news_items)
            description = str(metadata.get("description", "")).strip()
            description = description.replace("\\n", "\n")
            if len(description) < 100:
                description = self._enhance_description(description, news_items)
            validated["description"] = description
            tags = metadata.get("tags", [])
            if isinstance(tags, list):
                cleaned_tags = []
                for tag in tags[:20]:
                    clean_tag = str(tag).strip()
                    if clean_tag and len(clean_tag) <= 50:
                        cleaned_tags.append(clean_tag)
                validated["tags"] = cleaned_tags
            else:
                validated["tags"] = self._generate_fallback_tags(news_items)
            validated["category"] = str(metadata.get("category", "News & Politics"))
            validated["thumbnail_text"] = str(metadata.get("thumbnail_text", "経済ニュース"))
            validated["seo_keywords"] = metadata.get("seo_keywords", [])
            validated["target_audience"] = str(metadata.get("target_audience", "経済に関心のある視聴者"))
            validated["estimated_watch_time"] = str(metadata.get("estimated_watch_time", "15-30分"))
            validated["generated_at"] = datetime.now().isoformat()
            validated["news_count"] = len(news_items)
            return validated
        except Exception as e:
            logger.error(f"Metadata validation error: {e}")
            return self._get_fallback_metadata(news_items, "daily")

    def _generate_fallback_title(self, news_items: List[Dict[str, Any]]) -> str:
        """フォールバック用タイトル生成"""
        current_date = datetime.now().strftime("%m/%d")
        if news_items and len(news_items) > 0:
            main_topic = news_items[0].get("title", "経済ニュース")
            keywords = self._extract_keywords(main_topic)
            if keywords:
                return f"【{current_date}】{keywords[0]}など重要経済ニュース解説"
        return f"【{current_date}】今日の重要経済ニュース解説"

    def _enhance_description(self, description: str, news_items: List[Dict[str, Any]]) -> str:
        """説明文を拡充"""
        current_date = datetime.now().strftime("%Y年%m月%d日")
        enhanced = f"{description}\n\n" if description else ""
        enhanced += f"""
【{current_date} 経済ニュース解説】

本日の重要な経済ニュースを専門家が分かりやすく解説します。

📈 今日のトピック：
"""
        for i, item in enumerate(news_items, 1):
            enhanced += f"{i}. {item.get('title', '無題')}\n"
        enhanced += """

🎯 この動画で学べること：
• 最新の経済動向と市場への影響
• 専門家による詳細分析と解説
• 今後の注目ポイントと投資判断材料

📊 信頼できる情報源：
"""
        sources = set()
        for item in news_items:
            source = item.get("source")
            if source and source != "システム":
                sources.add(source)
        for source in list(sources)[:5]:
            enhanced += f"• {source}\n"
        enhanced += """

⚠️ 免責事項：
本動画の内容は情報提供を目的としており、投資勧誘ではありません。
投資判断は自己責任で行ってください。

#経済ニュース #投資 #株式市場 #金融 #経済解説
"""
        return enhanced

    def _generate_fallback_tags(self, news_items: List[Dict[str, Any]]) -> List[str]:
        """フォールバック用タグ生成"""
        base_tags = ["経済ニュース", "投資", "株式市場", "金融", "経済解説", "マーケット", "経済分析", "ニュース解説"]
        for item in news_items:
            title = item.get("title", "")
            keywords = self._extract_keywords(title)
            base_tags.extend(keywords[:3])
        unique_tags = []
        for tag in base_tags:
            if tag not in unique_tags and len(tag) <= 50:
                unique_tags.append(tag)
        return unique_tags[:15]

    def _extract_keywords(self, text: str) -> List[str]:
        """テキストからキーワードを抽出"""
        economic_patterns = [
            r"日経平均",
            r"TOPIX",
            r"ダウ",
            r"ナスダック",
            r"金利",
            r"インフレ",
            r"GDP",
            r"失業率",
            r"中央銀行",
            r"日銀",
            r"FRB",
            r"ECB",
            r"株価",
            r"為替",
            r"円安",
            r"円高",
            r"企業決算",
            r"業績",
            r"売上",
            r"利益",
            r"新規上場",
            r"IPO",
            r"M&A",
            r"買収",
        ]
        keywords = []
        for pattern in economic_patterns:
            if re.search(pattern, text):
                keywords.append(pattern.replace(r"\b", "").replace(r"\\", ""))
        return keywords[:5]

    def _get_fallback_metadata(self, news_items: List[Dict[str, Any]], mode: str) -> Dict[str, Any]:
        """フォールバック用メタデータ"""
        current_date = datetime.now().strftime("%Y年%m月%d日")
        return {
            "title": f"【{current_date}】重要経済ニュース解説",
            "description": f"""
【{current_date} 経済ニュース解説】

本日の重要な経済ニュースを専門家が分かりやすく解説します。

📈 今日のトピック：
"""
            + "\n".join([f"• {item.get('title', '無題')}" for item in news_items[:3]])
            + """

🎯 この動画で学べること：
• 最新の経済動向と市場への影響
• 専門家による詳細分析と解説
• 今後の注目ポイント

⚠️ 免責事項：
本動画の内容は情報提供を目的としており、投資勧誘ではありません。

#経済ニュース #投資 #株式市場 #金融 #経済解説""",
            "tags": self._generate_fallback_tags(news_items),
            "category": "News & Politics",
            "thumbnail_text": "経済ニュース解説",
            "seo_keywords": ["経済ニュース", "投資", "株式市場", "金融"],
            "target_audience": "経済に関心のある視聴者",
            "estimated_watch_time": "15-30分",
            "generated_at": datetime.now().isoformat(),
            "news_count": len(news_items),
            "fallback": True,
        }

    def create_short_form_metadata(self, topic: str, duration_minutes: int = 1) -> Dict[str, Any]:
        """ショート動画用メタデータ生成"""
        prompt = f"""
以下のトピックについて、YouTube Shorts用のメタデータを生成してください：

トピック: {topic}
動画長: {duration_minutes}分

要件：
- タイトル: 30文字以内、インパクト重視
- 説明文: 500文字以内、簡潔で興味を引く
- タグ: ショート動画向け、10個程度
- ハッシュタグ: トレンド性重視

JSON形式で回答してください：
{{
  "title": "ショート動画タイトル",
  "description": "簡潔な説明文",
  "tags": ["タグ1", "タグ2", ...],
  "hashtags": ["#ハッシュタグ1", "#ハッシュタグ2", ...],
  "category": "News & Politics"
}}
"""
        try:
            response = self._call_gemini_for_metadata(prompt)
            metadata = self._parse_metadata_response(response)
            if metadata:
                metadata["video_type"] = "shorts"
                metadata["estimated_watch_time"] = f"{duration_minutes}分"
                metadata["generated_at"] = datetime.now().isoformat()
            return metadata or self._get_fallback_shorts_metadata(topic)
        except Exception as e:
            logger.error(f"Failed to generate shorts metadata: {e}")
            return self._get_fallback_shorts_metadata(topic)

    def _get_fallback_shorts_metadata(self, topic: str) -> Dict[str, Any]:
        """ショート動画用フォールバックメタデータ"""
        return {
            "title": f"【速報】{topic}",
            "description": f"{topic}について1分で解説\n\n#経済ニュース #投資 #ショート動画",
            "tags": ["経済ニュース", "投資", "ショート", "速報", topic],
            "hashtags": ["#経済ニュース", "#投資", "#ショート動画", "#速報"],
            "category": "News & Politics",
            "video_type": "shorts",
            "estimated_watch_time": "1分",
            "generated_at": datetime.now().isoformat(),
            "fallback": True,
        }


# グローバルインスタンス
metadata_generator = MetadataGenerator() if cfg.gemini_api_key else None


def generate_youtube_metadata(
    news_items: List[Dict[str, Any]], script_content: str = "", mode: str = "daily"
) -> Dict[str, Any]:
    """YouTube メタデータ生成の簡易関数"""
    if metadata_generator:
        return metadata_generator.generate_youtube_metadata(news_items, script_content, mode)
    else:
        logger.warning("Metadata generator not available, using fallback")
        return MetadataGenerator()._get_fallback_metadata(news_items, mode)


def create_shorts_metadata(topic: str, duration_minutes: int = 1) -> Dict[str, Any]:
    """ショート動画メタデータ生成の簡易関数"""
    if metadata_generator:
        return metadata_generator.create_short_form_metadata(topic, duration_minutes)
    else:
        logger.warning("Metadata generator not available, using fallback")
        return MetadataGenerator()._get_fallback_shorts_metadata(topic)


if __name__ == "__main__":
    print("Testing metadata generation...")
    if cfg.gemini_api_key:
        test_news = [
            {
                "title": "日経平均株価が3日連続で上昇、年初来高値を更新",
                "summary": "東京株式市場で日経平均株価が前日比1.8%上昇し、3日連続の上昇となった。好調な企業決算と海外投資家の買いが支えとなり、年初来高値を更新した。",
                "source": "日本経済新聞",
                "impact_level": "high",
                "category": "金融",
            },
            {
                "title": "中央銀行が政策金利を0.25%引き上げ",
                "summary": "日本銀行は金融政策決定会合で政策金利を0.25%引き上げることを決定。インフレ抑制を目的とした措置で、市場は事前に織り込んでいた。",
                "source": "Bloomberg",
                "impact_level": "high",
                "category": "政策",
            },
        ]
        try:
            generator = MetadataGenerator()
            print("\n=== 通常動画メタデータ生成テスト ===")
            metadata = generator.generate_youtube_metadata(test_news, "", "daily")
            print(f"タイトル: {metadata.get('title')}")
            print(f"タグ数: {len(metadata.get('tags', []))}")
            print(f"説明文長: {len(metadata.get('description', ''))}")
            print(f"カテゴリ: {metadata.get('category')}")
            print("\n=== ショート動画メタデータ生成テスト ===")
            shorts_metadata = generator.create_short_form_metadata("日経平均高値更新", 1)
            print(f"ショートタイトル: {shorts_metadata.get('title')}")
            print(f"ハッシュタグ: {shorts_metadata.get('hashtags')}")
            print(f"動画タイプ: {shorts_metadata.get('video_type')}")
        except Exception as e:
            print(f"Test failed: {e}")
    else:
        print("Gemini API not configured, skipping test")

    print("\n=== フォールバック機能テスト ===")
    fallback_generator = MetadataGenerator()
    fallback_metadata = fallback_generator._get_fallback_metadata([], "daily")
    print(f"フォールバックタイトル: {fallback_metadata.get('title')}")
    print(f"フォールバックタグ数: {len(fallback_metadata.get('tags', []))}")
