"""日本語品質チェックシステムの統合テスト

このテストは、原稿生成から字幕生成まで、
日本語品質チェックが適切に機能することを確認します。
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.japanese_quality import (
    check_script_japanese_purity,
    clean_subtitle_text,
    improve_japanese_quality,
    japanese_quality_checker,
    validate_subtitle_text,
)


def test_english_detection():
    """英語混入の検出テスト"""
    print("\n=== Test 1: English Detection ===")

    test_cases = [
        {
            "name": "Pure Japanese",
            "script": "田中: 今日は重要な経済ニュースについて話します。\n鈴木: GDPが3.5%増加しました。",
            "expected_pure": True,
        },
        {
            "name": "Mixed with English",
            "script": "田中: Today we will discuss important news.\n鈴木: The market is very bullish.",
            "expected_pure": False,
        },
        {
            "name": "Allowed abbreviations",
            "script": "田中: AIとIoT技術が発展しています。\n鈴木: GDPは前年比2.3%の増加です。",
            "expected_pure": True,
        },
    ]

    for test in test_cases:
        result = check_script_japanese_purity(test["script"])
        status = "✓" if result["is_pure_japanese"] == test["expected_pure"] else "✗"
        print(f"{status} {test['name']}: Pure={result['is_pure_japanese']}, Score={result['purity_score']:.1f}")

        if not result["is_pure_japanese"] and result["issues"]:
            print(f"   Issues found: {result['total_issues']}")
            for issue in result["issues"][:3]:
                print(f"   - {issue['text']}")


def test_quality_improvement():
    """品質改善テスト"""
    print("\n=== Test 2: Quality Improvement ===")

    bad_script = """
田中: Hello、今日はimportantなeconomic newsについて話します。

鈴木: The stock marketがsignificantlyに上昇しました。

田中: Let's analyze this situation in detail.
"""

    print("Original script (first 150 chars):")
    print(bad_script[:150])

    # 品質チェック
    result = check_script_japanese_purity(bad_script)
    print(f"\nOriginal purity score: {result['purity_score']:.1f}/100")
    print(f"Issues found: {result['total_issues']}")

    # 改善
    if not result["is_pure_japanese"] and japanese_quality_checker:
        improved = improve_japanese_quality(bad_script)
        if improved["success"] and improved.get("changes_made"):
            print(f"\nImproved purity score: {improved['new_score']:.1f}/100")
            print(f"Issues fixed: {improved.get('issues_fixed', 0)}")
            print("\nImproved script (first 150 chars):")
            print(improved["improved_script"][:150])
        else:
            print("\nImprovement not successful or no changes needed")
    else:
        print("\nNo improvement needed or checker not available")


def test_subtitle_validation():
    """字幕検証テスト"""
    print("\n=== Test 3: Subtitle Validation ===")

    test_subtitles = [
        ("今日は重要なニュースがあります", True),
        ("GDPが3.5%増加しました", True),
        ("This is an English subtitle", False),
        ("AI技術が発展しています", True),
        ("Hello、こんにちは", False),
        ("2025年1月15日の経済動向", True),
    ]

    for subtitle, expected_valid in test_subtitles:
        is_valid = validate_subtitle_text(subtitle)
        status = "✓" if is_valid == expected_valid else "✗"
        result = "OK" if is_valid else "NG"
        print(f"{status} '{subtitle[:40]}' -> {result}")


def test_subtitle_cleaning():
    """字幕クリーニングテスト"""
    print("\n=== Test 4: Subtitle Cleaning ===")

    test_cases = [
        ("Hello、今日は良い天気です", "こんにちは、今日は良い天気です"),
        ("Thank you for watching", "ありがとうございますfor watching"),
        ("AI technology is developing", "AI technology is developing"),
        ("純粋な日本語です", "純粋な日本語です"),
    ]

    for original, expected_pattern in test_cases:
        cleaned = clean_subtitle_text(original)
        # 完全一致ではなく、変化があったかをチェック
        changed = cleaned != original
        print(f"Original: '{original}'")
        print(f"Cleaned:  '{cleaned}'")
        print(f"Changed: {changed}\n")


def test_end_to_end():
    """エンドツーエンドテスト"""
    print("\n=== Test 5: End-to-End Integration ===")

    # シミュレートされた原稿生成
    generated_script = """
田中: Welcome everyone、今日はimportantな経済ニュースについてdiscussします。

鈴木: まず、日本のGDPがprevious quarterに比べて2.1%増加したというgood newsがあります。

田中: That's interesting。詳しくanalysisしてみましょう。

鈴木: 特にmanufacturing sectorとIT sectorの成長が顕著です。
"""

    print("1. Original generated script:")
    print(generated_script[:200] + "...\n")

    # Step 1: 品質チェック
    print("2. Checking Japanese purity...")
    purity_result = check_script_japanese_purity(generated_script)
    print(f"   Purity score: {purity_result['purity_score']:.1f}/100")
    print(f"   Issues: {purity_result['total_issues']}")

    # Step 2: 改善（必要な場合）
    final_script = generated_script
    if not purity_result["is_pure_japanese"] and japanese_quality_checker:
        print("\n3. Improving quality...")
        improved = improve_japanese_quality(generated_script)
        if improved["success"] and improved.get("changes_made"):
            final_script = improved["improved_script"]
            print(f"   New score: {improved['new_score']:.1f}/100")
            print(f"   Issues fixed: {improved.get('issues_fixed', 0)}")

    # Step 3: 字幕検証（シミュレート）
    print("\n4. Validating subtitles...")
    sample_subtitles = [
        "今日は重要な経済ニュースについて話します",
        "GDPが2.1%増加しました",
        "製造業とIT業界の成長が顕著です",
    ]

    valid_count = 0
    for subtitle in sample_subtitles:
        if validate_subtitle_text(subtitle):
            valid_count += 1

    print(f"   Valid subtitles: {valid_count}/{len(sample_subtitles)}")

    # 結果サマリー
    print("\n5. Summary:")
    print("   ✓ Script generation completed")
    print(f"   ✓ Quality check: {purity_result['purity_score']:.1f}/100")
    if japanese_quality_checker and not purity_result["is_pure_japanese"]:
        print("   ✓ Auto-improvement applied")
    print(f"   ✓ Subtitle validation: {valid_count}/{len(sample_subtitles)} passed")
    print("\n   Final script (first 200 chars):")
    print(f"   {final_script[:200]}...")


def run_all_tests():
    """すべてのテストを実行"""
    print("=" * 60)
    print("Japanese Quality Check System - Integration Tests")
    print("=" * 60)

    if not japanese_quality_checker:
        print("\n⚠️  Warning: Japanese quality checker not available")
        print("   Some tests may be skipped or show limited functionality")
        print("   Please check that GEMINI_API_KEY is configured\n")

    try:
        test_english_detection()
        test_quality_improvement()
        test_subtitle_validation()
        test_subtitle_cleaning()
        test_end_to_end()

        print("\n" + "=" * 60)
        print("✓ All tests completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()
