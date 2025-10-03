"""Pixabay API統合テスト"""

import os
from pathlib import Path

import pytest


@pytest.mark.api
@pytest.mark.requires_api_key
@pytest.mark.stock_footage
def test_pixabay_api_key_loaded(has_pixabay_key):
    """Pixabay APIキーが読み込まれているか確認"""
    if not has_pixabay_key:
        pytest.skip("Pixabay APIキーが設定されていません")

    pixabay_key = os.getenv("PIXABAY_API_KEY")
    assert pixabay_key is not None, "PIXABAY_API_KEYが設定されていません"
    assert len(pixabay_key) > 10, "PIXABAY_API_KEYが短すぎます"


@pytest.mark.api
@pytest.mark.requires_api_key
@pytest.mark.stock_footage
@pytest.mark.slow
def test_pixabay_video_search(has_pixabay_key):
    """Pixabayから動画を検索できるか確認"""
    if not has_pixabay_key:
        pytest.skip("Pixabay APIキーが設定されていません")

    from app.services.media.stock_footage_manager import StockFootageManager

    # Pexelsキーを一時的に無効化してPixabayのみをテスト
    saved_pexels = os.environ.pop("PEXELS_API_KEY", None)

    try:
        manager = StockFootageManager()
        keywords = ["economy", "stock market"]

        results = manager.search_footage(keywords, max_clips=3)

        assert len(results) > 0, "検索結果が0件です"
        assert all(v["source"] == "pixabay" for v in results), "Pixabay以外のソースが混入しています"

        # 最初の結果の構造確認
        first_result = results[0]
        assert "keyword" in first_result
        assert "url" in first_result
        assert "quality" in first_result
        assert "duration" in first_result
        assert "width" in first_result
        assert "height" in first_result

    finally:
        # Pexelsキーを復元
        if saved_pexels:
            os.environ["PEXELS_API_KEY"] = saved_pexels


@pytest.mark.api
@pytest.mark.requires_api_key
@pytest.mark.stock_footage
@pytest.mark.slow
def test_pixabay_video_quality(has_pixabay_key):
    """Pixabayから高品質動画が取得できるか確認"""
    if not has_pixabay_key:
        pytest.skip("Pixabay APIキーが設定されていません")

    from app.services.media.stock_footage_manager import StockFootageManager

    # Pexelsキーを一時的に無効化
    saved_pexels = os.environ.pop("PEXELS_API_KEY", None)

    try:
        manager = StockFootageManager()
        results = manager.search_footage(["business"], max_clips=3)

        assert len(results) > 0, "検索結果が0件です"

        # HD品質（1920x1080以上）が含まれるか確認
        hd_videos = [v for v in results if v["width"] >= 1920 and v["height"] >= 1080]
        assert len(hd_videos) > 0, "HD品質の動画が見つかりませんでした"

    finally:
        if saved_pexels:
            os.environ["PEXELS_API_KEY"] = saved_pexels


@pytest.mark.api
@pytest.mark.requires_api_key
@pytest.mark.stock_footage
@pytest.mark.slow
@pytest.mark.e2e
def test_pixabay_video_download(has_pixabay_key, temp_output_dir):
    """Pixabayから動画をダウンロードできるか確認"""
    if not has_pixabay_key:
        pytest.skip("Pixabay APIキーが設定されていません")

    from app.services.media.stock_footage_manager import StockFootageManager

    # Pexelsキーを一時的に無効化
    saved_pexels = os.environ.pop("PEXELS_API_KEY", None)

    try:
        manager = StockFootageManager()
        results = manager.search_footage(["technology"], max_clips=1)

        assert len(results) > 0, "検索結果が0件です"

        video = results[0]
        download_path = manager.download_clip(video)

        assert download_path is not None, "ダウンロードに失敗しました"
        assert Path(download_path).exists(), "ダウンロードされたファイルが存在しません"

        # ファイルサイズ確認（0バイトでないこと）
        file_size = Path(download_path).stat().st_size
        assert file_size > 0, "ダウンロードされたファイルが空です"

    finally:
        if saved_pexels:
            os.environ["PEXELS_API_KEY"] = saved_pexels
