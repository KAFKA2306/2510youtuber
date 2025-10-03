"""API Key Rotationのテスト"""

import os

import pytest

from app.api_rotation import APIKey  # APIKeyをファイルの先頭でインポート


@pytest.mark.api
@pytest.mark.requires_api_key
def test_rotation_manager_initialization():
    """APIローテーションマネージャーが初期化できるか確認"""
    from app.api_rotation import get_rotation_manager

    manager = get_rotation_manager()

    assert manager is not None, "ローテーションマネージャーが初期化されませんでした"


@pytest.mark.api
@pytest.mark.requires_api_key
def test_gemini_key_registration(has_gemini_key):
    """Geminiキーが登録できるか確認"""
    if not has_gemini_key:
        pytest.skip("Gemini APIキーが設定されていません")

    from app.api_rotation import get_rotation_manager

    manager = get_rotation_manager()

    # Geminiキーとキー名を収集 (GEMINI_API_KEY_2から5を対象)
    gemini_keys_with_names = []
    for i in range(2, 6):  # GEMINI_API_KEY_1はスキップ
        key_name = f"GEMINI_API_KEY_{i}"
        key_value = os.getenv(key_name)
        if key_value and "your-" not in key_value:
            gemini_keys_with_names.append((key_name, key_value))

    if gemini_keys_with_names:
        manager.register_keys("gemini", gemini_keys_with_names)
        stats = manager.get_stats("gemini")

        assert stats["total_keys"] == len(gemini_keys_with_names), "登録されたキー数が一致しません"
        assert stats["available_keys"] > 0, "利用可能なキーがありません"

        # 登録されたキーのkey_nameが正しく設定されていることを確認
        for i, key_obj in enumerate(manager.key_pools["gemini"]):
            expected_key_name = f"GEMINI_API_KEY_{i+2}"  # インデックス調整
            assert key_obj.key_name == expected_key_name, f"キー {key_obj.key} のkey_nameが正しくありません"
    else:
        pytest.skip("GEMINI_API_KEY_2から5が設定されていません")


@pytest.mark.api
def test_rotation_manager_stats():
    """ローテーションマネージャーの統計情報が取得できるか確認"""
    from app.api_rotation import get_rotation_manager

    manager = get_rotation_manager()

    # テスト用のダミーキーを登録
    test_keys_with_names = [("TEST_KEY_1", "test_key_1"), ("TEST_KEY_2", "test_key_2"), ("TEST_KEY_3", "test_key_3")]
    manager.register_keys("test_service", test_keys_with_names)

    stats = manager.get_stats("test_service")

    assert stats is not None, "統計情報が取得できませんでした"
    assert "total_keys" in stats, "統計情報にtotal_keysがありません"
    assert "available_keys" in stats, "統計情報にavailable_keysがありません"
    assert stats["total_keys"] == 3, "登録されたキー数が一致しません"


@pytest.mark.api
def test_key_rotation_mechanism():
    """キーローテーション機構が動作するか確認"""
    from app.api_rotation import get_rotation_manager

    manager = get_rotation_manager()

    # テスト用のダミーキーを登録
    test_keys_with_names = [("ROTATION_KEY_1", "key_1"), ("ROTATION_KEY_2", "key_2"), ("ROTATION_KEY_3", "key_3")]
    manager.register_keys("rotation_test", test_keys_with_names)

    # キーを順次取得
    key1 = manager.get_best_key("rotation_test").key
    key2 = manager.get_best_key("rotation_test").key
    key3 = manager.get_best_key("rotation_test").key

    # test_keys_with_namesからキーの値だけを抽出
    test_keys_values = [key_value for _, key_value in test_keys_with_names]

    # すべて有効なキーが取得できることを確認
    assert key1 in test_keys_values, "取得されたキーが登録されたキーに含まれていません"
    assert key2 in test_keys_values, "取得されたキーが登録されたキーに含まれていません"
    assert key3 in test_keys_values, "取得されたキーが登録されたキーに含まれていません"


@pytest.mark.api
def test_gemini_daily_quota_limit_exceeded():
    """Geminiの日次クォータ制限に達したときにExceptionが発生することを確認"""
    import datetime
    from unittest.mock import MagicMock

    from app.api_rotation import APIKeyRotationManager

    manager = APIKeyRotationManager()
    manager.register_keys("gemini", [("GEMINI_API_KEY_2", "key2")])  # GEMINI_API_KEY_2を使用
    manager.set_gemini_daily_quota_limit(1)  # 制限を1に設定
    manager.gemini_daily_calls = 0
    manager.last_quota_reset_date = datetime.datetime.now() - datetime.timedelta(days=1)  # リセットを強制

    mock_api_call = MagicMock(return_value="Success")

    # 1回目の呼び出しは成功
    manager.execute_with_rotation("gemini", mock_api_call)
    assert manager.gemini_daily_calls == 1

    # 2回目の呼び出しは制限超過で失敗
    with pytest.raises(Exception, match="Gemini daily quota .* exceeded"):
        manager.execute_with_rotation("gemini", mock_api_call)
    assert manager.gemini_daily_calls == 1  # 失敗してもカウントは増えない


@pytest.mark.api
def test_gemini_daily_quota_reset():
    """日付が変わるとGeminiの日次クォータがリセットされることを確認"""
    import datetime
    from unittest.mock import MagicMock

    from app.api_rotation import APIKeyRotationManager

    manager = APIKeyRotationManager()
    manager.register_keys("gemini", [("GEMINI_API_KEY_2", "key2")])  # GEMINI_API_KEY_2を使用
    manager.set_gemini_daily_quota_limit(1)  # 制限を1に設定
    manager.gemini_daily_calls = 1
    manager.last_quota_reset_date = datetime.datetime.now() - datetime.timedelta(days=1)  # リセットを強制

    mock_api_call = MagicMock(return_value="Success")

    # 日付が変わったので、クォータがリセットされ、呼び出しが成功する
    manager.execute_with_rotation("gemini", mock_api_call)
    assert manager.gemini_daily_calls == 1  # リセット後、1回目の呼び出し
    assert manager.last_quota_reset_date.date() == datetime.datetime.now().date()


@pytest.mark.api
def test_log_output_contains_key_name(caplog):
    """ログ出力にkey_nameが含まれることを確認"""
    import logging
    from unittest.mock import MagicMock

    from app.api_rotation import APIKeyRotationManager

    manager = APIKeyRotationManager()
    manager.key_pools["test_service"] = [
        APIKey(
            key="test_key_value_1", provider="test_service", key_name="TEST_API_KEY_1"
        )  # APIKeyRotationManager.APIKey を APIKey に変更
    ]
    manager.current_indices["test_service"] = 0

    mock_api_call = MagicMock(return_value="Success")

    with caplog.at_level(logging.INFO):
        manager.execute_with_rotation("test_service", mock_api_call)
        assert "TEST_API_KEY_1" in caplog.text
        assert "API call succeeded with TEST_API_KEY_1" in caplog.text

    with caplog.at_level(logging.WARNING):
        mock_api_call.side_effect = Exception("Rate limit error")
        with pytest.raises(Exception):
            manager.execute_with_rotation("test_service", mock_api_call)
        assert "TEST_API_KEY_1 API call failed" in caplog.text
