"""Visual keyword extraction from Japanese news scripts.

日本語のニューススクリプトから視覚的なキーワードを抽出し、
適切なストック映像検索用の英語キーワードに変換します。
"""

import logging
import re
from typing import Dict, List, Set

logger = logging.getLogger(__name__)


class VisualMatcher:
    """Extract visual keywords from Japanese script for stock footage search."""

    # 日本語 → 英語ビジュアルキーワードマッピング
    KEYWORD_MAP = {
        # 経済・金融
        "経済": ["economy", "business", "finance"],
        "金融": ["finance", "banking", "financial"],
        "株式": ["stock market", "trading", "stocks"],
        "市場": ["market", "trading floor", "exchange"],
        "株価": ["stock chart", "market data", "trading screen"],
        "投資": ["investment", "investor", "portfolio"],
        "証券": ["securities", "stock exchange", "trading"],

        # 通貨・為替
        "円": ["japanese yen", "currency", "forex"],
        "ドル": ["dollar", "currency exchange", "forex"],
        "円高": ["currency exchange", "forex trading", "yen"],
        "円安": ["currency exchange", "forex trading", "yen"],
        "為替": ["foreign exchange", "forex", "currency"],

        # 中央銀行・政策
        "日銀": ["bank of japan", "central bank", "monetary policy"],
        "FRB": ["federal reserve", "central bank", "monetary policy"],
        "金利": ["interest rates", "financial charts", "economy"],
        "政策": ["government", "policy", "meeting"],

        # 企業・ビジネス
        "企業": ["corporate", "office", "business meeting"],
        "会社": ["company", "corporate office", "business"],
        "業績": ["business performance", "charts", "analytics"],
        "決算": ["financial report", "business meeting", "charts"],
        "売上": ["sales", "business growth", "charts"],

        # 都市・場所
        "東京": ["tokyo", "cityscape", "japan"],
        "大阪": ["osaka", "cityscape", "japan"],
        "日本": ["japan", "tokyo", "japanese"],
        "アメリカ": ["united states", "new york", "washington"],
        "中国": ["china", "shanghai", "beijing"],

        # トレンド・動き
        "上昇": ["upward trend", "growth", "rising"],
        "下落": ["downward trend", "decline", "falling"],
        "成長": ["growth", "expansion", "success"],
        "回復": ["recovery", "improvement", "growth"],
        "急騰": ["surge", "spike", "rapid growth"],
        "暴落": ["crash", "collapse", "decline"],

        # 産業
        "製造": ["manufacturing", "factory", "production"],
        "自動車": ["automotive", "cars", "manufacturing"],
        "電子": ["electronics", "technology", "manufacturing"],
        "半導体": ["semiconductor", "technology", "microchip"],
        "AI": ["artificial intelligence", "technology", "computer"],
        "IT": ["information technology", "computer", "digital"],

        # 資源・エネルギー
        "石油": ["oil", "energy", "petroleum"],
        "原油": ["crude oil", "oil rig", "energy"],
        "電力": ["electricity", "power plant", "energy"],
        "再生": ["renewable energy", "solar", "wind power"],

        # その他
        "グラフ": ["chart", "graph", "data visualization"],
        "データ": ["data", "analytics", "statistics"],
        "会議": ["meeting", "conference", "business discussion"],
        "発表": ["announcement", "presentation", "conference"],
    }

    # カテゴリー別のデフォルトキーワード
    DEFAULT_KEYWORDS = {
        "economy": ["economy", "finance", "business analytics"],
        "market": ["stock market", "trading", "financial charts"],
        "business": ["corporate office", "business meeting", "skyline"],
        "technology": ["technology", "digital", "computer"],
        "generic": ["business", "professional", "modern office"],
    }

    def __init__(self):
        """Initialize visual matcher."""
        self.last_extraction_stats = {}

    def extract_keywords(
        self,
        script_content: str,
        news_items: List[Dict] = None,
        max_keywords: int = 5,
    ) -> List[str]:
        """Extract visual keywords from Japanese script and news items.

        Args:
            script_content: Japanese script text
            news_items: List of news item dicts with 'title' and 'summary'
            max_keywords: Maximum number of keywords to return

        Returns:
            List of English keywords for stock footage search
        """
        keywords = set()
        matched_terms = []

        # Extract from script
        if script_content:
            script_keywords, script_matches = self._extract_from_text(script_content)
            keywords.update(script_keywords)
            matched_terms.extend(script_matches)

        # Extract from news items
        if news_items:
            for item in news_items:
                title = item.get("title", "")
                summary = item.get("summary", "")

                title_keywords, title_matches = self._extract_from_text(title)
                keywords.update(title_keywords)
                matched_terms.extend(title_matches)

                summary_keywords, summary_matches = self._extract_from_text(summary)
                keywords.update(summary_keywords)
                matched_terms.extend(summary_matches)

        # Convert to list and prioritize
        keyword_list = list(keywords)

        # If no keywords found, use defaults based on common terms
        if not keyword_list:
            category = self._detect_category(script_content, news_items)
            keyword_list = self.DEFAULT_KEYWORDS.get(category, self.DEFAULT_KEYWORDS["generic"])
            logger.warning(f"No specific keywords found, using default '{category}' keywords")

        # Store stats
        self.last_extraction_stats = {
            "total_keywords": len(keyword_list),
            "matched_japanese_terms": len(set(matched_terms)),
            "japanese_terms": matched_terms[:10],  # First 10 for reference
        }

        # Limit and return
        result = keyword_list[:max_keywords]
        logger.info(f"Extracted visual keywords: {result} (from {len(matched_terms)} Japanese terms)")
        return result

    def _extract_from_text(self, text: str) -> tuple[Set[str], List[str]]:
        """Extract keywords from a single text string.

        Returns:
            Tuple of (keyword set, matched Japanese terms list)
        """
        keywords = set()
        matched_terms = []

        for jp_term, en_terms in self.KEYWORD_MAP.items():
            if jp_term in text:
                keywords.update(en_terms[:2])  # Take first 2 terms per match
                matched_terms.append(jp_term)

        return keywords, matched_terms

    def _detect_category(self, script_content: str, news_items: List[Dict] = None) -> str:
        """Detect content category when no specific keywords found.

        Returns:
            Category name for default keyword selection
        """
        text = script_content or ""

        if news_items:
            for item in news_items:
                text += " " + item.get("title", "") + " " + item.get("summary", "")

        # Simple category detection
        if any(term in text for term in ["株", "市場", "取引", "投資"]):
            return "market"
        elif any(term in text for term in ["IT", "AI", "技術", "デジタル"]):
            return "technology"
        elif any(term in text for term in ["企業", "会社", "ビジネス"]):
            return "business"
        else:
            return "economy"

    def get_extraction_stats(self) -> Dict:
        """Get statistics from last extraction.

        Returns:
            Dict with extraction statistics
        """
        return self.last_extraction_stats.copy()

    def add_custom_mapping(self, japanese_term: str, english_keywords: List[str]):
        """Add custom Japanese → English keyword mapping.

        Args:
            japanese_term: Japanese term to match
            english_keywords: List of English keywords to use
        """
        self.KEYWORD_MAP[japanese_term] = english_keywords
        logger.info(f"Added custom mapping: {japanese_term} → {english_keywords}")

    def suggest_keywords(self, text: str, top_n: int = 10) -> List[tuple]:
        """Suggest possible keywords based on text analysis.

        Args:
            text: Japanese text to analyze
            top_n: Number of suggestions to return

        Returns:
            List of (japanese_term, english_keywords, count) tuples
        """
        suggestions = []

        for jp_term, en_terms in self.KEYWORD_MAP.items():
            count = text.count(jp_term)
            if count > 0:
                suggestions.append((jp_term, en_terms, count))

        # Sort by frequency
        suggestions.sort(key=lambda x: x[2], reverse=True)
        return suggestions[:top_n]


if __name__ == "__main__":
    # Test the visual matcher
    matcher = VisualMatcher()

    # Sample Japanese script
    sample_script = """
    田中: 今日の日経平均株価は大きく上昇しましたね。
    鈴木: はい、特にIT関連企業の株価が急騰しています。
    田中: 円安の影響もありますね。ドル円相場は150円を突破しました。
    鈴木: 日銀の金融政策も注目されています。
    """

    sample_news = [
        {
            "title": "日経平均が史上最高値を更新",
            "summary": "東京株式市場で日経平均株価が大幅に上昇し、史上最高値を更新した。",
        },
        {
            "title": "円安進行、1ドル150円台に",
            "summary": "外国為替市場で円安が進行し、1ドル=150円台をつけた。",
        },
    ]

    print("\n=== Visual Keyword Extraction Test ===")
    print(f"\nScript preview: {sample_script[:100]}...")
    print(f"News items: {len(sample_news)}")

    keywords = matcher.extract_keywords(sample_script, sample_news, max_keywords=5)

    print(f"\n✓ Extracted keywords: {keywords}")

    stats = matcher.get_extraction_stats()
    print(f"\nStatistics:")
    print(f"  - Total keywords: {stats['total_keywords']}")
    print(f"  - Matched terms: {stats['matched_japanese_terms']}")
    print(f"  - Japanese terms: {stats['japanese_terms']}")

    print("\n=== Keyword Suggestions ===")
    suggestions = matcher.suggest_keywords(sample_script, top_n=5)
    for jp_term, en_terms, count in suggestions:
        print(f"  {jp_term} ({count}x) → {', '.join(en_terms[:3])}")
