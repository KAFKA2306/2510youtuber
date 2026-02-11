"""Reusable prompt fragments and language-policy constants."""
from __future__ import annotations
from typing import Iterable, Sequence, Tuple
DEFAULT_VIDEO_MODE_CONTEXT = "経済ニュース解説動画"
METADATA_MODE_CONTEXT = {
    "daily": "日次の経済ニュース解説動画",
    "special": "特集・深堀り解説動画",
    "breaking": "速報・緊急ニュース動画",
}
METADATA_REQUIREMENTS_LINES: Tuple[str, ...] = (
    "1. タイトル: 50文字以内、**キャッチーでWOW感のあるタイトル**",
    "2. 説明文: 1000-3000文字、SEO最適化",
    "3. タグ: 15-20個、検索性向上",
    "4. カテゴリ: YouTube標準カテゴリ",
    "5. サムネイル文言: 大きく表示するテキスト",
)
METADATA_TITLE_POLICY_LINES: Tuple[str, ...] = (
    "✅ **クリック率を最大化する要素を含める:**",
    "  - 数字・パーセンテージ（例: \"10%急騰\"、\"3日連続\"）",
    "  - 緊急性・時事性（例: \"速報\"、\"緊急\"、\"今日の\"）",
    "  - 感情を刺激する言葉（例: \"衝撃\"、\"注目\"、\"警告\"、\"チャンス\"）",
    "  - 疑問形・問いかけ（例: \"なぜ？\"、\"どうなる？\"）",
    "  - 具体的な固有名詞（例: \"日経平均\"、\"日銀\"、\"NVIDIA\"）",
)
METADATA_TITLE_SUCCESS_EXAMPLES: Tuple[str, ...] = (
    '\"【速報】日経平均10%急騰！その理由と今後の展開\"',
    '\"日銀緊急利上げ！株価暴落のシナリオとは？\"',
    '\"NVIDIA決算で市場激変！今注目すべき3銘柄\"',
    '\"円安150円突破！あなたの資産への影響は？\"',
)
METADATA_TITLE_AVOID_EXAMPLES: Tuple[str, ...] = (
    '\"今日の経済ニュース解説\"（平凡すぎ）',
    '\"市場動向について\"（抽象的）',
    '\"経済情報まとめ\"（興味を引かない）',
)
METADATA_OTHER_POLICIES_LINES: Tuple[str, ...] = (
    "- 正確性と信頼性を最優先（誇張しすぎない）",
    "- 検索されやすいキーワードを含める",
    "- 視聴者価値を明確に示す",
    "- 時事性を強調",
)
JAPANESE_LANGUAGE_RULES: Tuple[str, ...] = (
    "すべての内容を純粋な日本語で記述してください",
    "英語の単語や表現を使用しないでください",
    "専門用語は理解しやすい日本語で説明してください",
    "AI、GDP、ITなどの一般的な略語のみ使用可能",
)
JAPANESE_DIALOGUE_FORMAT = "田中: [発言内容]\n鈴木: [発言内容]"
PURE_JAPANESE_DIRECTIVE = "すべて純粋な日本語で記述し、英語を使用しない"
JAPANESE_PURITY_IMPROVEMENT_STEPS: Tuple[str, ...] = (
    PURE_JAPANESE_DIRECTIVE,
    "すべての英語単語を適切な日本語に翻訳または言い換える",
    JAPANESE_LANGUAGE_RULES[2],
    "会話の自然さを保つ",
    "話者名（田中:、鈴木:）のフォーマットは維持する",
    "数字、パーセント、単位（円、ドルなど）はそのまま使用可能",
    JAPANESE_LANGUAGE_RULES[3],
)
JAPANESE_ALLOWED_PATTERNS: Tuple[str, ...] = (
    r"\\d+",
    r"\\d+%",
    r"\\d+円",
    r"\\d+ドル",
    r"\\d+年",
    r"\\d+月",
    r"\\d+日",
    r"GDP",
    r"AI",
    r"IT",
    r"IoT",
    r"DX",
)
JAPANESE_ALLOWED_ECONOMIC_ACRONYMS = frozenset(
    {
        "Fed",
        "QE",
        "GDP",
        "CPI",
        "PPI",
        "ECB",
        "BOJ",
        "IMF",
        "OECD",
        "WTO",
        "OPEC",
        "G7",
        "G20",
        "BRICS",
        "ASEAN",
        "ETF",
        "REIT",
        "ESG",
        "IPO",
        "M&A",
        "CEO",
        "CFO",
        "CTO",
        "AI",
        "IT",
        "DX",
        "IoT",
        "API",
        "SaaS",
        "FinTech",
        "VC",
        "PE",
        "ROE",
        "ROI",
        "PER",
        "PBR",
        "EPS",
        "FOMC",
        "RBNZ",
        "SNB",
        "BOE",
        "RBA",
    }
)
def join_lines(lines: Sequence[str]) -> str:
    """Return a newline-joined string for the provided sequence of lines."""
    return "\n".join(lines)
def indent_lines(lines: Iterable[str], prefix: str = "  ") -> str:
    """Indent each line with *prefix* and return the joined string."""
    return "\n".join(f"{prefix}{line}" for line in lines)
def bullet_lines(lines: Sequence[str], bullet: str = "- ") -> str:
    """Render *lines* as a bullet list using *bullet* as the prefix."""
    return "\n".join(f"{bullet}{line}" for line in lines)
def numbered_lines(lines: Sequence[str], start: int = 1, delimiter: str = ". ") -> str:
    """Render *lines* as a numbered list with the provided *delimiter*."""
    return "\n".join(f"{index}{delimiter}{line}" for index, line in enumerate(lines, start))
