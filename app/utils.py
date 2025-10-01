"""ユーティリティモジュール

共通的な便利関数とヘルパー機能を提供します。
"""

import logging
import os
import re
import tempfile
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class FileUtils:
    """ファイル操作ユーティリティ"""

    @staticmethod
    def ensure_directory(path: str) -> str:
        """ディレクトリが存在することを保証"""
        os.makedirs(path, exist_ok=True)
        return path

    @staticmethod
    def safe_filename(filename: str, max_length: int = 100) -> str:
        """安全なファイル名を生成"""
        safe_name = re.sub(r'[<>:"/\\|?*]', "_", filename)
        safe_name = re.sub(r"\s+", "_", safe_name)
        safe_name = safe_name.strip("._")
        if len(safe_name) > max_length:
            name, ext = os.path.splitext(safe_name)
            safe_name = name[: max_length - len(ext)] + ext
        return safe_name or "untitled"

    @staticmethod
    def get_temp_file(prefix: str = "temp_", suffix: str = ".tmp") -> str:
        """一時ファイルパスを生成"""
        FileUtils.ensure_directory("temp")
        return tempfile.mktemp(suffix=suffix, prefix=prefix, dir="temp")


class TextUtils:
    """テキスト処理ユーティリティ"""

    @staticmethod
    def clean_text(text: str) -> str:
        """テキストをクリーニング"""
        if not text:
            return ""
        cleaned = text.strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = re.sub(r"\n\s*\n\s*\n+", "\n\n", cleaned)
        return cleaned


class DateUtils:
    """日付・時刻ユーティリティ"""

    @staticmethod
    def get_jst_now() -> datetime:
        """JST現在時刻を取得"""
        jst = timedelta(hours=9)
        return datetime.now(timezone(jst))

    @staticmethod
    def format_duration(seconds: float) -> str:
        """秒数を読みやすい形式にフォーマット"""
        if seconds < 60:
            return f"{seconds:.1f}秒"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}分"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}時間"
