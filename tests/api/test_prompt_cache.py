"""プロンプトキャッシュのテスト"""

import pytest


@pytest.mark.api
def test_prompt_cache_initialization():
    """プロンプトキャッシュが初期化できるか確認"""
    from app.prompt_cache import get_prompt_cache

    cache = get_prompt_cache()

    assert cache is not None, "プロンプトキャッシュが初期化されませんでした"


@pytest.mark.api
def test_prompt_cache_save_and_load():
    """プロンプトの保存と読み込みができるか確認"""
    from app.prompt_cache import get_prompt_cache

    cache = get_prompt_cache()

    # テスト用プロンプトを保存
    test_prompts = {
        "prompt_a": "テストプロンプトA: ニュース収集",
        "prompt_b": "テストプロンプトB: 台本生成",
        "prompt_c": "テストプロンプトC: 品質チェック"
    }

    success = cache.save_prompts("test_mode", test_prompts)
    assert success is True, "プロンプトの保存に失敗しました"

    # 読み込みテスト
    loaded = cache.load_prompts("test_mode")
    assert loaded is not None, "プロンプトの読み込みに失敗しました"
    assert loaded.get("prompt_a") == test_prompts["prompt_a"], "保存したプロンプトと一致しません"
    assert loaded.get("prompt_b") == test_prompts["prompt_b"], "保存したプロンプトと一致しません"
    assert loaded.get("prompt_c") == test_prompts["prompt_c"], "保存したプロンプトと一致しません"


@pytest.mark.api
def test_prompt_cache_status():
    """キャッシュステータスが取得できるか確認"""
    from app.prompt_cache import get_prompt_cache

    cache = get_prompt_cache()

    # テスト用プロンプトを保存
    test_prompts = {"test_key": "test_value"}
    cache.save_prompts("status_test", test_prompts)

    # ステータス取得
    status = cache.get_cache_status()

    assert status is not None, "キャッシュステータスが取得できませんでした"
    assert 'cached_modes' in status, "cached_modesがステータスに含まれていません"


@pytest.mark.api
def test_prompt_cache_multiple_modes():
    """複数のモードでキャッシュが独立して動作するか確認"""
    from app.prompt_cache import get_prompt_cache

    cache = get_prompt_cache()

    # 異なるモードで異なるプロンプトを保存
    prompts_mode1 = {"key": "value_mode1"}
    prompts_mode2 = {"key": "value_mode2"}

    cache.save_prompts("mode1", prompts_mode1)
    cache.save_prompts("mode2", prompts_mode2)

    # 各モードから読み込み
    loaded_mode1 = cache.load_prompts("mode1")
    loaded_mode2 = cache.load_prompts("mode2")

    assert loaded_mode1.get("key") == "value_mode1", "mode1のプロンプトが正しくありません"
    assert loaded_mode2.get("key") == "value_mode2", "mode2のプロンプトが正しくありません"
    assert loaded_mode1.get("key") != loaded_mode2.get("key"), "異なるモードのプロンプトが混在しています"


@pytest.mark.api
def test_prompt_cache_overwrite():
    """既存のキャッシュを上書きできるか確認"""
    from app.prompt_cache import get_prompt_cache

    cache = get_prompt_cache()

    # 最初のプロンプトを保存
    prompts_v1 = {"version": "1"}
    cache.save_prompts("overwrite_test", prompts_v1)

    # 同じモードで別のプロンプトを保存（上書き）
    prompts_v2 = {"version": "2"}
    cache.save_prompts("overwrite_test", prompts_v2)

    # 読み込み
    loaded = cache.load_prompts("overwrite_test")

    assert loaded.get("version") == "2", "上書きが正しく機能していません"
