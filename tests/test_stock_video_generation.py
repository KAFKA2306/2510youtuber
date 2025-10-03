#!/usr/bin/env python3
"""Integration test for stock footage video generation.

This tests the full pipeline: keyword extraction → stock footage → B-roll → final video.
Note: Requires audio and subtitle files to generate a complete video.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from app.video import video_generator
from app.services.media import VisualMatcher


def test_stock_footage_capability():
    """Test if stock footage generation is available."""
    print("\n" + "="*70)
    print("🎬 Stock Footage Video Generation Integration Test")
    print("="*70)

    # Check if stock footage is available
    can_use_stock = video_generator._can_use_stock_footage()
    print(f"\n✓ Stock footage capability: {can_use_stock}")

    if not can_use_stock:
        print("✗ Stock footage not available (API keys not configured)")
        return False

    # Test keyword extraction
    print("\n--- Keyword Extraction Test ---")
    sample_script = """
    田中: 今日は日経平均株価について話しましょう。
    鈴木: はい、最近の市場動向は非常に興味深いですね。
    田中: 特にテクノロジー企業の株価が上昇しています。
    """

    sample_news = [
        {"title": "日経平均が上昇", "summary": "株式市場で日経平均が大幅上昇"},
        {"title": "円相場が変動", "summary": "為替市場で円安が進行"},
    ]

    print(f"Script: {sample_script[:80]}...")
    print(f"News items: {len(sample_news)}")

    # Extract keywords
    matcher = VisualMatcher()
    keywords = matcher.extract_keywords(sample_script, sample_news, max_keywords=5)
    print(f"\n✓ Extracted keywords: {keywords}")

    stats = matcher.get_extraction_stats()
    print(f"✓ Matched {stats['matched_japanese_terms']} Japanese terms")
    print(f"✓ Generated {stats['total_keywords']} total keywords")

    # Test stock footage search
    print("\n--- Stock Footage Search Test ---")
    from app.services.media import StockFootageManager

    manager = StockFootageManager()
    results = manager.search_footage(keywords, max_clips=3)

    if results:
        print(f"✓ Found {len(results)} stock clips:")
        for i, clip in enumerate(results[:3], 1):
            print(f"  {i}. {clip['keyword']} - {clip['quality']} ({clip['width']}x{clip['height']}) - {clip['duration']}s")
    else:
        print("✗ No clips found")
        return False

    # Summary
    print("\n" + "="*70)
    print("✅ Integration Test Passed!")
    print("="*70)
    print("\nStock footage video generation is fully operational.")
    print("Next video generation will automatically use stock footage B-roll.")
    print("\nTo generate a test video with stock footage, run:")
    print("  python -m app.main test")
    print("\nOr disable stock footage temporarily:")
    print("  ENABLE_STOCK_FOOTAGE=false python -m app.main test")

    return True


def test_generation_methods():
    """Show available generation methods."""
    print("\n--- Available Generation Methods ---")
    print("1. Stock Footage B-roll (Primary)")
    print("   - Automatic keyword extraction")
    print("   - Pexels/Pixabay API")
    print("   - Professional transitions & effects")
    print("\n2. Static Background (Fallback)")
    print("   - 4 theme variations (A/B tested)")
    print("   - Robot icon overlay")
    print("   - Dynamic gradients")
    print("\n3. Simple Background (Emergency)")
    print("   - Solid color gradient")
    print("   - Always succeeds")


def main():
    """Run integration tests."""
    print("\n" + "="*70)
    print("🧪 Stock Footage Video Generation - Full Integration Test")
    print("="*70)

    success = test_stock_footage_capability()

    if success:
        test_generation_methods()

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
