"""API Key Rotationのテスト"""

import os
import pytest


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

    # Geminiキーを収集
    gemini_keys = []
    for i in range(1, 6):
        key_name = f'GEMINI_API_KEY_{i}' if i > 1 else 'GEMINI_API_KEY'
        key = os.getenv(key_name)
        if key and 'your-' not in key:
            gemini_keys.append(key)

    if gemini_keys:
        manager.register_keys("gemini", gemini_keys)
        stats = manager.get_stats("gemini")

        assert stats['total_keys'] == len(gemini_keys), "登録されたキー数が一致しません"
        assert stats['available_keys'] > 0, "利用可能なキーがありません"


@pytest.mark.api
def test_rotation_manager_stats():
    """ローテーションマネージャーの統計情報が取得できるか確認"""
    from app.api_rotation import get_rotation_manager

    manager = get_rotation_manager()

    # テスト用のダミーキーを登録
    test_keys = ["test_key_1", "test_key_2", "test_key_3"]
    manager.register_keys("test_service", test_keys)

    stats = manager.get_stats("test_service")

    assert stats is not None, "統計情報が取得できませんでした"
    assert 'total_keys' in stats, "統計情報にtotal_keysがありません"
    assert 'available_keys' in stats, "統計情報にavailable_keysがありません"
    assert stats['total_keys'] == 3, "登録されたキー数が一致しません"


@pytest.mark.api
def test_key_rotation_mechanism():
    """キーローテーション機構が動作するか確認"""
    from app.api_rotation import get_rotation_manager

    manager = get_rotation_manager()

    # テスト用のダミーキーを登録
    test_keys = ["key_1", "key_2", "key_3"]
    manager.register_keys("rotation_test", test_keys)

    # キーを順次取得
    key1 = manager.get_best_key("rotation_test").key
    key2 = manager.get_best_key("rotation_test").key
    key3 = manager.get_best_key("rotation_test").key

    # すべて有効なキーが取得できることを確認
    assert key1 in test_keys, "取得されたキーが登録されたキーに含まれていません"
    assert key2 in test_keys, "取得されたキーが登録されたキーに含まれていません"
    assert key3 in test_keys, "取得されたキーが登録されたキーに含まれていません"


@pytest.mark.api
def test_gemini_daily_quota_limit_exceeded():
    """Geminiの日次クォータ制限に達したときにExceptionが発生することを確認"""
    from app.api_rotation import APIKeyRotationManager
    from unittest.mock import MagicMock
    import datetime

    manager = APIKeyRotationManager()
    manager.register_keys("gemini", ["key1"])
    manager.set_gemini_daily_quota_limit(1)  # 制限を1に設定
    manager.gemini_daily_calls = 0
    manager.last_quota_reset_date = datetime.datetime.now() - datetime.timedelta(days=1) # リセットを強制

    mock_api_call = MagicMock(return_value="Success")

    # 1回目の呼び出しは成功
    manager.execute_with_rotation("gemini", mock_api_call)
    assert manager.gemini_daily_calls == 1

    # 2回目の呼び出しは制限超過で失敗
    with pytest.raises(Exception, match="Gemini daily quota .* exceeded"):
        manager.execute_with_rotation("gemini", mock_api_call)
    assert manager.gemini_daily_calls == 1 # 失敗してもカウントは増えない


@pytest.mark.api
def test_gemini_daily_quota_reset():
    """日付が変わるとGeminiの日次クォータがリセットされることを確認"""
    from app.api_rotation import APIKeyRotationManager
    from unittest.mock import MagicMock
    import datetime

    manager = APIKeyRotationManager()
    manager.register_keys("gemini", ["key1"])
    manager.set_gemini_daily_quota_limit(1)  # 制限を1に設定
    manager.gemini_daily_calls = 1
    manager.last_quota_reset_date = datetime.datetime.now() - datetime.timedelta(days=1) # リセットを強制

    mock_api_call = MagicMock(return_value="Success")

    # 日付が変わったので、クォータがリセットされ、呼び出しが成功する
    manager.execute_with_rotation("gemini", mock_api_call)
    assert manager.gemini_daily_calls == 1 # リセット後、1回目の呼び出し
    assert manager.last_quota_reset_date.date() == datetime.datetime.now().date()
