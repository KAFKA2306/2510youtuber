"""
ユーティリティモジュール

共通的な便利関数とヘルパー機能を提供します。
"""

import os
import re
import json
import time
import hashlib
import logging
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

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
        # 危険な文字を除去
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', filename)
        safe_name = re.sub(r'\s+', '_', safe_name)
        safe_name = safe_name.strip('._')

        # 長さ制限
        if len(safe_name) > max_length:
            name, ext = os.path.splitext(safe_name)
            safe_name = name[:max_length-len(ext)] + ext

        return safe_name or "untitled"

    @staticmethod
    def get_file_hash(filepath: str, algorithm: str = "md5") -> str:
        """ファイルのハッシュ値を計算"""
        hash_algo = hashlib.new(algorithm)

        try:
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_algo.update(chunk)
            return hash_algo.hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate hash for {filepath}: {e}")
            return ""

    @staticmethod
    def get_file_info(filepath: str) -> Dict[str, Any]:
        """ファイル情報を取得"""
        try:
            stat = os.stat(filepath)
            return {
                'path': filepath,
                'name': os.path.basename(filepath),
                'size': stat.st_size,
                'size_mb': stat.st_size / (1024 * 1024),
                'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'extension': Path(filepath).suffix.lower(),
                'exists': True
            }
        except Exception as e:
            return {
                'path': filepath,
                'exists': False,
                'error': str(e)
            }

    @staticmethod
    def cleanup_old_files(directory: str, days_old: int = 7, pattern: str = "*") -> int:
        """古いファイルを削除"""
        cleaned_count = 0
        cutoff_time = time.time() - (days_old * 24 * 60 * 60)

        try:
            for file_path in Path(directory).glob(pattern):
                if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                    try:
                        file_path.unlink()
                        cleaned_count += 1
                        logger.debug(f"Deleted old file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to delete {file_path}: {e}")
        except Exception as e:
            logger.error(f"Failed to cleanup directory {directory}: {e}")

        return cleaned_count

class TextUtils:
    """テキスト処理ユーティリティ"""

    @staticmethod
    def clean_text(text: str) -> str:
        """テキストをクリーニング"""
        if not text:
            return ""

        # 基本的なクリーニング
        cleaned = text.strip()
        cleaned = re.sub(r'\s+', ' ', cleaned)  # 複数空白を単一に
        cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned)  # 複数改行を2つに

        return cleaned

    @staticmethod
    def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
        """テキストを指定長に切り詰め"""
        if len(text) <= max_length:
            return text

        return text[:max_length - len(suffix)] + suffix

    @staticmethod
    def extract_keywords(text: str, min_length: int = 3) -> List[str]:
        """テキストからキーワードを抽出"""
        # 単語を抽出
        words = re.findall(r'\b\w+\b', text.lower())

        # フィルタリング
        keywords = []
        stop_words = {'の', 'に', 'は', 'を', 'が', 'で', 'と', 'から', 'まで', 'より', 'について'}

        for word in words:
            if len(word) >= min_length and word not in stop_words:
                if word not in keywords:
                    keywords.append(word)

        return keywords[:20]  # 最大20個

    @staticmethod
    def count_japanese_chars(text: str) -> Dict[str, int]:
        """日本語文字数をカウント"""
        hiragana = len(re.findall(r'[ひらがな]', text))
        katakana = len(re.findall(r'[カタカナ]', text))
        kanji = len(re.findall(r'[一-龯]', text))

        return {
            'hiragana': hiragana,
            'katakana': katakana,
            'kanji': kanji,
            'total_japanese': hiragana + katakana + kanji,
            'total_chars': len(text)
        }

    @staticmethod
    def estimate_reading_time(text: str, chars_per_minute: int = 400) -> float:
        """読み上げ時間を推定（分）"""
        char_count = len(text)
        return char_count / chars_per_minute

class DateUtils:
    """日付・時刻ユーティリティ"""

    @staticmethod
    def get_jst_now() -> datetime:
        """JST現在時刻を取得"""
        from datetime import timezone
        jst = timezone(timedelta(hours=9))
        return datetime.now(jst)

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

    @staticmethod
    def get_business_day(offset: int = 0) -> datetime:
        """営業日を取得（土日を除く）"""
        current = datetime.now().date()

        while offset != 0:
            if offset > 0:
                current += timedelta(days=1)
                if current.weekday() < 5:  # 月-金
                    offset -= 1
            else:
                current -= timedelta(days=1)
                if current.weekday() < 5:  # 月-金
                    offset += 1

        return datetime.combine(current, datetime.min.time())

    @staticmethod
    def is_market_open(dt: datetime = None) -> bool:
        """市場開場時間かどうかを判定"""
        if dt is None:
            dt = DateUtils.get_jst_now()

        # 土日は休場
        if dt.weekday() >= 5:
            return False

        # 9:00-15:00 (JST) が開場時間
        market_open = dt.replace(hour=9, minute=0, second=0, microsecond=0)
        market_close = dt.replace(hour=15, minute=0, second=0, microsecond=0)

        return market_open <= dt <= market_close

class JsonUtils:
    """JSON処理ユーティリティ"""

    @staticmethod
    def safe_load(data: Union[str, bytes, dict]) -> dict:
        """安全なJSON読み込み"""
        if isinstance(data, dict):
            return data

        try:
            if isinstance(data, bytes):
                data = data.decode('utf-8')
            return json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(f"Failed to parse JSON: {e}")
            return {}

    @staticmethod
    def safe_dump(data: Any, indent: int = 2) -> str:
        """安全なJSON出力"""
        try:
            return json.dumps(data, ensure_ascii=False, indent=indent)
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to serialize JSON: {e}")
            return "{}"

    @staticmethod
    def merge_dicts(dict1: dict, dict2: dict, deep: bool = True) -> dict:
        """辞書をマージ"""
        if not deep:
            result = dict1.copy()
            result.update(dict2)
            return result

        result = dict1.copy()
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = JsonUtils.merge_dicts(result[key], value, deep=True)
            else:
                result[key] = value

        return result

class RetryUtils:
    """リトライ処理ユーティリティ"""

    @staticmethod
    def with_retry(func, max_retries: int = 3, delay: float = 1.0,
                   backoff: float = 2.0, exceptions: tuple = (Exception,)):
        """リトライデコレータ"""
        def wrapper(*args, **kwargs):
            current_delay = delay

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries - 1:
                        raise

                    logger.warning(f"Attempt {attempt + 1} failed: {e}, retrying in {current_delay}s...")
                    time.sleep(current_delay)
                    current_delay *= backoff

            return None

        return wrapper

    @staticmethod
    async def async_with_retry(func, max_retries: int = 3, delay: float = 1.0,
                              backoff: float = 2.0, exceptions: tuple = (Exception,)):
        """非同期リトライ"""
        import asyncio

        current_delay = delay

        for attempt in range(max_retries):
            try:
                return await func()
            except exceptions as e:
                if attempt == max_retries - 1:
                    raise

                logger.warning(f"Async attempt {attempt + 1} failed: {e}, retrying in {current_delay}s...")
                await asyncio.sleep(current_delay)
                current_delay *= backoff

        return None

class ValidationUtils:
    """バリデーションユーティリティ"""

    @staticmethod
    def validate_url(url: str) -> bool:
        """URL形式を検証"""
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        return bool(url_pattern.match(url))

    @staticmethod
    def validate_email(email: str) -> bool:
        """メールアドレス形式を検証"""
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        return bool(email_pattern.match(email))

    @staticmethod
    def validate_video_file(filepath: str) -> Dict[str, Any]:
        """動画ファイルを検証"""
        result = {
            'valid': False,
            'file_exists': False,
            'file_size': 0,
            'extension': '',
            'errors': []
        }

        try:
            if not os.path.exists(filepath):
                result['errors'].append("File does not exist")
                return result

            result['file_exists'] = True

            file_info = FileUtils.get_file_info(filepath)
            result['file_size'] = file_info['size']
            result['extension'] = file_info['extension']

            # 拡張子チェック
            valid_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
            if result['extension'] not in valid_extensions:
                result['errors'].append(f"Invalid extension: {result['extension']}")

            # ファイルサイズチェック (256GB制限)
            max_size = 256 * 1024 * 1024 * 1024
            if result['file_size'] > max_size:
                result['errors'].append(f"File too large: {result['file_size']} bytes")

            # 最小サイズチェック (1KB)
            if result['file_size'] < 1024:
                result['errors'].append(f"File too small: {result['file_size']} bytes")

            result['valid'] = len(result['errors']) == 0

        except Exception as e:
            result['errors'].append(f"Validation error: {e}")

        return result

class TemplateUtils:
    """テンプレート処理ユーティリティ"""

    @staticmethod
    def render_template(template: str, variables: Dict[str, Any]) -> str:
        """シンプルなテンプレート処理"""
        result = template

        for key, value in variables.items():
            placeholder = f"{{{key}}}"
            result = result.replace(placeholder, str(value))

        return result

    @staticmethod
    def get_email_template(template_name: str, variables: Dict[str, Any] = None) -> str:
        """メールテンプレートを取得"""
        templates = {
            'success': """
✅ YouTube動画生成が完了しました

実行ID: {run_id}
実行時間: {execution_time}
動画URL: {video_url}
生成ファイル数: {file_count}

詳細は管理画面でご確認ください。
""",
            'error': """
❌ YouTube動画生成でエラーが発生しました

実行ID: {run_id}
エラー内容: {error_message}
失敗ステップ: {failed_step}

システム管理者にお問い合わせください。
""",
            'warning': """
⚠️ YouTube動画生成で警告が発生しました

実行ID: {run_id}
警告内容: {warning_message}
影響: {impact}

処理は継続されましたが、確認をお願いします。
"""
        }

        template = templates.get(template_name, templates['error'])
        variables = variables or {}

        return TemplateUtils.render_template(template, variables)

# モジュールレベルの便利関数
def get_temp_file(suffix: str = "", prefix: str = "youtuber_") -> str:
    """一時ファイルパスを生成"""
    with tempfile.NamedTemporaryFile(suffix=suffix, prefix=prefix, delete=False) as f:
        return f.name

def measure_time(func):
    """実行時間測定デコレータ"""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time

        logger.info(f"{func.__name__} executed in {execution_time:.2f}s")
        return result

    return wrapper

async def async_measure_time(func):
    """非同期実行時間測定デコレータ"""
    import asyncio

    async def wrapper(*args, **kwargs):
        start_time = time.time()
        result = await func(*args, **kwargs)
        execution_time = time.time() - start_time

        logger.info(f"{func.__name__} executed in {execution_time:.2f}s")
        return result

    return wrapper

def log_function_call(func):
    """関数呼び出しログデコレータ"""
    def wrapper(*args, **kwargs):
        logger.debug(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")

        try:
            result = func(*args, **kwargs)
            logger.debug(f"{func.__name__} completed successfully")
            return result
        except Exception as e:
            logger.error(f"{func.__name__} failed: {e}")
            raise

    return wrapper

if __name__ == "__main__":
    # テスト実行
    print("Testing utility functions...")

    # ファイルユーティリティテスト
    print("\n=== File Utils Test ===")
    test_filename = FileUtils.safe_filename("危険な<ファイル>名?.txt")
    print(f"Safe filename: {test_filename}")

    # テキストユーティリティテスト
    print("\n=== Text Utils Test ===")
    test_text = "これは　　テスト　　　テキストです。\n\n\n\n長い文章を短くします。"
    cleaned = TextUtils.clean_text(test_text)
    print(f"Cleaned text: {cleaned}")

    truncated = TextUtils.truncate_text("これは長いテキストの例です", 10)
    print(f"Truncated: {truncated}")

    keywords = TextUtils.extract_keywords("経済ニュース 株価 投資 金融 市場")
    print(f"Keywords: {keywords}")

    # 日付ユーティリティテスト
    print("\n=== Date Utils Test ===")
    jst_now = DateUtils.get_jst_now()
    print(f"JST Now: {jst_now}")

    duration_str = DateUtils.format_duration(3661)
    print(f"Duration: {duration_str}")

    market_open = DateUtils.is_market_open()
    print(f"Market open: {market_open}")

    # JSONユーティリティテスト
    print("\n=== JSON Utils Test ===")
    test_dict = {"key1": "value1", "nested": {"key2": "value2"}}
    json_str = JsonUtils.safe_dump(test_dict)
    print(f"JSON dump: {json_str}")

    loaded_dict = JsonUtils.safe_load(json_str)
    print(f"JSON load: {loaded_dict}")

    # バリデーションテスト
    print("\n=== Validation Test ===")
    url_valid = ValidationUtils.validate_url("https://example.com")
    print(f"URL valid: {url_valid}")

    email_valid = ValidationUtils.validate_email("test@example.com")
    print(f"Email valid: {email_valid}")

    # テンプレートテスト
    print("\n=== Template Test ===")
    template = "Hello {name}, your score is {score}"
    rendered = TemplateUtils.render_template(template, {"name": "Alice", "score": 95})
    print(f"Rendered template: {rendered}")

    print("\nUtility functions test completed.")