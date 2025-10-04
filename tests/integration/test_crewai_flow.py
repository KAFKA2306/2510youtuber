#!/usr/bin/env python3
"""CrewAI WOW Script Creation Flow テスト

簡易テスト用のニュースアイテムを使ってCrewAIフローをテスト
"""

import asyncio
import logging
import sys
from pathlib import Path

import pytest

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.crew.flows import create_wow_script_crew

pytestmark = [
    pytest.mark.integration,
    pytest.mark.crewai,
    pytest.mark.requires_api_key,
    pytest.mark.slow,
]

# ロギング設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)


# テスト用のサンプルニュース
SAMPLE_NEWS = [
    {
        "title": "日銀、金融政策の転換を示唆",
        "url": "https://example.com/news1",
        "summary": "日本銀行が長年続けてきた超低金利政策からの転換を示唆する発言が注目を集めている。",
        "key_points": [
            "植田総裁が政策見直しの可能性に言及",
            "インフレ率が目標の2%に近づく",
            "市場では利上げ観測が強まる",
        ],
        "impact_level": "high",
        "category": "経済",
    },
    {
        "title": "新NISAが投資ブームを加速",
        "url": "https://example.com/news2",
        "summary": "2024年に始まった新NISA制度により、個人投資家の参入が急増している。",
        "key_points": ["口座開設数が前年比200%増", "若年層の投資参加が顕著", "長期積立投資が人気"],
        "impact_level": "medium",
        "category": "経済",
    },
    {
        "title": "AI関連株が市場を牽引",
        "url": "https://example.com/news3",
        "summary": "生成AIブームにより、AI関連企業の株価が急騰している。",
        "key_points": ["NVIDIA株価が年初来で300%上昇", "日本のAI関連銘柄も連動上昇", "投資家の関心が集中"],
        "impact_level": "high",
        "category": "経済",
    },
]


@pytest.mark.asyncio
async def test_crewai_flow(has_gemini_key):
    """CrewAI Flowのテスト実行"""
    if not has_gemini_key:
        pytest.skip("Gemini APIキーが設定されていません")

    logger.info("=" * 60)
    logger.info("🧪 CrewAI WOW Script Creation Flow テスト開始")
    logger.info("=" * 60)

    try:
        # CrewAI Flow実行
        logger.info("\n📋 テストニュース:")
        for i, news in enumerate(SAMPLE_NEWS, 1):
            logger.info(f"  {i}. {news['title']}")

        logger.info("\n🚀 CrewAI実行中...")
        result = create_wow_script_crew(news_items=SAMPLE_NEWS, target_duration_minutes=8)

        # 結果表示
        logger.info("\n" + "=" * 60)
        logger.info("✅ テスト完了")
        logger.info("=" * 60)

        if result.get("success"):
            logger.info("\n🎉 SUCCESS!")
            logger.info(f"\n📝 生成された台本 ({len(result.get('final_script', ''))} 文字):")
            logger.info("-" * 60)
            print(result.get("final_script", ""))
            logger.info("-" * 60)

            # 結果をファイルに保存
            output_file = project_root / "output" / "test_crewai_script.txt"
            output_file.parent.mkdir(exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(result.get("final_script", ""))
            logger.info(f"\n💾 台本を保存: {output_file}")

        else:
            logger.error("\n❌ FAILED!")
            logger.error(f"エラー: {result.get('error', 'Unknown error')}")
            return 1

        return 0

    except Exception as e:
        logger.error(f"\n❌ テスト失敗: {e}", exc_info=True)
        return 1


def main():
    """メイン実行"""
    exit_code = asyncio.run(test_crewai_flow())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
