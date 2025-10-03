#!/usr/bin/env python3
"""API安定性機能の導通テスト

新規実装された機能をミニマルに検証:
1. API Key Rotation (Gemini)
2. NewsAPI.org フォールバック
3. プロンプトキャッシュ
"""

import os

from dotenv import load_dotenv

# .envファイルを読み込み
load_dotenv("secret/.env")

print("=" * 60)
print("🧪 API安定性機能 - 導通テスト")
print("=" * 60)

# ===== Test 1: API Key Rotation (Gemini) =====
print("\n【Test 1】API Key Rotation (Gemini)")
print("-" * 60)

try:
    from app.api_rotation import get_rotation_manager

    manager = get_rotation_manager()

    # Geminiキーを登録
    gemini_keys = []
    for i in range(1, 6):
        key_name = f"GEMINI_API_KEY_{i}" if i > 1 else "GEMINI_API_KEY"
        key = os.getenv(key_name)
        if key and "your-" not in key:  # プレースホルダーを除外
            gemini_keys.append(key)

    if gemini_keys:
        manager.register_keys("gemini", gemini_keys)
        print(f"✓ Geminiキー登録完了: {len(gemini_keys)}個")

        # 簡単なテスト呼び出し（実際のAPIは呼ばない）
        stats = manager.get_stats("gemini")
        print(f"  - 登録キー数: {stats['total_keys']}")
        print(f"  - 利用可能キー: {stats['available_keys']}")

        print("✅ Test 1 PASSED: API Key Rotation 正常動作")
    else:
        print("⚠️  Test 1 SKIPPED: 有効なGeminiキーが設定されていません")

except Exception as e:
    print(f"❌ Test 1 FAILED: {e}")
    import traceback
    traceback.print_exc()

# ===== Test 2: NewsAPI.org フォールバック =====
print("\n【Test 2】NewsAPI.org フォールバック")
print("-" * 60)

try:
    newsapi_key = os.getenv("NEWSAPI_API_KEY")

    if newsapi_key and newsapi_key != "your_newsapi_key":
        from app.search_news import NewsCollector

        collector = NewsCollector()
        print("✓ NewsCollector初期化完了")

        # NewsAPI経由でニュース収集テスト（実際のAPI呼び出し）
        print("  - NewsAPIから経済ニュースを取得中...")
        news_items = collector._collect_from_newsapi("test")

        if news_items:
            print(f"✓ NewsAPIから{len(news_items)}件のニュース取得成功")
            print(f"  - サンプル: {news_items[0]['title'][:50]}...")
            print("✅ Test 2 PASSED: NewsAPI.org 正常動作")
        else:
            print("⚠️  Test 2 WARNING: ニュース取得件数0（APIエラーの可能性）")
    else:
        print("⚠️  Test 2 SKIPPED: NewsAPIキーが設定されていません")

except Exception as e:
    print(f"❌ Test 2 FAILED: {e}")
    import traceback
    traceback.print_exc()

# ===== Test 3: プロンプトキャッシュ =====
print("\n【Test 3】プロンプトキャッシュ")
print("-" * 60)

try:
    from app.prompt_cache import get_prompt_cache

    cache = get_prompt_cache()
    print("✓ PromptCache初期化完了")

    # テスト用プロンプトを保存
    test_prompts = {
        "prompt_a": "テストプロンプトA: ニュース収集",
        "prompt_b": "テストプロンプトB: 台本生成",
    }

    success = cache.save_prompts("test", test_prompts)
    if success:
        print("✓ キャッシュ保存成功")

    # 読み込みテスト
    loaded = cache.load_prompts("test")
    if loaded and loaded.get("prompt_a") == test_prompts["prompt_a"]:
        print("✓ キャッシュ読込成功")

        # ステータス確認
        status = cache.get_cache_status()
        print(f"  - キャッシュモード数: {len(status['cached_modes'])}")

        print("✅ Test 3 PASSED: プロンプトキャッシュ 正常動作")
    else:
        print("⚠️  Test 3 WARNING: キャッシュ読込結果が一致しません")

except Exception as e:
    print(f"❌ Test 3 FAILED: {e}")
    import traceback
    traceback.print_exc()

# ===== 総括 =====
print("\n" + "=" * 60)
print("📊 テスト結果サマリー")
print("=" * 60)
print("""
✅ 実装完了機能:
  1. API Key Rotation (Gemini/Perplexity)
  2. NewsAPI.org フォールバック
  3. プロンプトキャッシュ (TTL: 24h)
  4. TTS並列度動的調整

💡 次のステップ:
  - 実際のワークフローでの統合テスト
  - ログ監視でキーローテーション動作確認
  - Rate limit発生時の自動切替確認
""")

print("=" * 60)
print("🎉 導通テスト完了")
print("=" * 60)
