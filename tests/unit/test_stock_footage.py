#!/usr/bin/env python3
"""Test script for stock footage integration.

Tests the new zero-cost stock footage B-roll feature.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()

from app.services.media import BRollGenerator, StockFootageManager, VisualMatcher


def test_config():
    """Test configuration."""
    print("\n" + "=" * 60)
    print("📋 Configuration Test")
    print("=" * 60)

    pexels_key = os.getenv("PEXELS_API_KEY", "")
    pixabay_key = os.getenv("PIXABAY_API_KEY", "")
    enable_stock = os.getenv("ENABLE_STOCK_FOOTAGE", "true").lower() == "true"

    print(f"\n✓ Pexels API Key: {'✓ Configured' if pexels_key else '✗ Not configured'}")
    print(f"✓ Pixabay API Key: {'✓ Configured' if pixabay_key else '✗ Not configured (optional)'}")
    print(f"✓ Stock Footage Enabled: {enable_stock}")

    if not pexels_key and not pixabay_key:
        print("\n⚠️  WARNING: No stock footage API keys configured")
        print("   Get free API keys from:")
        print("   - Pexels: https://www.pexels.com/api/")
        print("   - Pixabay: https://pixabay.com/api/docs/")
        return False

    return True


def test_visual_matcher():
    """Test visual keyword extraction."""
    print("\n" + "=" * 60)
    print("🎯 Visual Matcher Test")
    print("=" * 60)

    matcher = VisualMatcher()

    # Sample Japanese script
    sample_script = """
    武宏: 今日の日経平均株価は大きく上昇しましたね。
    つむぎ: はい、特にIT関連企業の株価が急騰しています。
    武宏: 円安の影響もありますね。ドル円相場は150円を突破しました。
    """

    sample_news = [
        {
            "title": "日経平均が史上最高値を更新",
            "summary": "東京株式市場で日経平均株価が大幅に上昇",
        }
    ]

    print(f"\n📝 Sample script: {sample_script[:80]}...")

    keywords = matcher.extract_keywords(sample_script, sample_news, max_keywords=5)

    print(f"\n✓ Extracted keywords: {keywords}")

    stats = matcher.get_extraction_stats()
    print(f"✓ Total keywords: {stats['total_keywords']}")
    print(f"✓ Matched terms: {stats['matched_japanese_terms']}")
    print(f"✓ Japanese terms: {stats['japanese_terms'][:5]}")

    return len(keywords) > 0


def test_stock_footage_manager():
    """Test stock footage search and download."""
    print("\n" + "=" * 60)
    print("📹 Stock Footage Manager Test")
    print("=" * 60)

    manager = StockFootageManager()

    keywords = ["economy", "finance", "business"]
    print(f"\n🔍 Searching for: {keywords}")

    try:
        results = manager.search_footage(keywords, max_clips=3)

        if not results:
            print("✗ No footage found (this may be normal if API keys not configured)")
            return False

        print(f"\n✓ Found {len(results)} clips:")
        for i, clip in enumerate(results, 1):
            print(f"\n  {i}. {clip['keyword']} ({clip['source']})")
            print(f"     Duration: {clip['duration']}s")
            print(f"     Quality: {clip['quality']} ({clip['width']}x{clip['height']})")

        # Test download of first clip
        if results:
            print("\n📥 Testing download of first clip...")
            path = manager.download_clip(results[0])
            if path:
                file_size_mb = os.path.getsize(path) / (1024 * 1024)
                print(f"✓ Downloaded: {path} ({file_size_mb:.1f} MB)")
                return True
            else:
                print("✗ Download failed")
                return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_broll_generator():
    """Test B-roll generation (requires downloaded clips)."""
    print("\n" + "=" * 60)
    print("🎬 B-roll Generator Test")
    print("=" * 60)

    _generator = BRollGenerator()
    print("✓ B-roll generator initialized")

    print("\nℹ️  Note: Full B-roll test requires actual video clips")
    print("   Run test_stock_footage_manager() first to download clips")

    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("🧪 Stock Footage Integration Test Suite")
    print("=" * 70)

    results = {
        "config": test_config(),
        "visual_matcher": test_visual_matcher(),
        "broll_generator": test_broll_generator(),
    }

    # Only test stock footage manager if configured
    if results["config"]:
        results["stock_footage_manager"] = test_stock_footage_manager()
    else:
        results["stock_footage_manager"] = None

    # Summary
    print("\n" + "=" * 70)
    print("📊 Test Summary")
    print("=" * 70)

    for test_name, result in results.items():
        if result is None:
            status = "⏭️  Skipped"
        elif result:
            status = "✅ Passed"
        else:
            status = "❌ Failed"

        print(f"{status} {test_name}")

    passed = sum(1 for r in results.values() if r is True)
    total = len([r for r in results.values() if r is not None])

    print(f"\n✓ {passed}/{total} tests passed")

    if not results["config"]:
        print("\n💡 Quick Start:")
        print("   1. Get free API key: https://www.pexels.com/api/")
        print("   2. Add to .env: PEXELS_API_KEY=your_key_here")
        print("   3. Run this test again")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
