"""
設定管理モジュール

環境変数からAPIキーやその他の設定を読み込み、アプリケーション全体で利用可能にします。
"""

import os
import json
import logging
from typing import List, Optional
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()

class Config:
    """アプリケーション設定クラス"""

    def __init__(self):
        self._setup_logging()
        self._validate_required_vars()

    # ===== AI APIs =====
    @property
    def anthropic_api_key(self) -> str:
        """Anthropic API キー"""
        return os.getenv('ANTHROPIC_API_KEY', '')

    @property
    def gemini_api_key(self) -> str:
        """Gemini API キー（メイン）"""
        return os.getenv('GEMINI_API_KEY', '')

    @property
    def gemini_api_keys(self) -> List[str]:
        """Gemini API キーリスト（並列処理用）"""
        keys = [
            os.getenv('GEMINI_API_KEY'),
            os.getenv('GEMINI_API_KEY_2'),
            os.getenv('GEMINI_API_KEY_3'),
        ]
        return [k for k in keys if k]

    @property
    def elevenlabs_api_key(self) -> str:
        """ElevenLabs API キー"""
        return os.getenv('ELEVENLABS_API_KEY', '')

    # ===== Google Services =====
    @property
    def google_credentials_json(self) -> dict:
        """Google認証情報（JSON）"""
        creds_str = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '{}')
        try:
            if creds_str.startswith('{'):
                # JSON文字列として解析
                return json.loads(creds_str)
            else:
                # ファイルパスとして扱う
                if os.path.exists(creds_str):
                    with open(creds_str, 'r') as f:
                        return json.load(f)
                else:
                    logging.warning(f"Google credentials file not found: {creds_str}")
                    return {}
        except json.JSONDecodeError as e:
            logging.error(f"Invalid Google credentials JSON: {e}")
            return {}

    @property
    def google_sheet_id(self) -> str:
        """Google Sheets ID"""
        return os.getenv('GOOGLE_SHEET_ID', '')

    @property
    def google_drive_folder_id(self) -> str:
        """Google Drive フォルダID"""
        return os.getenv('GOOGLE_DRIVE_FOLDER_ID', '')

    @property
    def youtube_client_secret(self) -> dict:
        """YouTube API クライアント設定"""
        secret_str = os.getenv('YOUTUBE_CLIENT_SECRET', '{}')
        try:
            if secret_str.startswith('{'):
                return json.loads(secret_str)
            else:
                # ファイルパスとして扱う
                if os.path.exists(secret_str):
                    with open(secret_str, 'r') as f:
                        return json.load(f)
                else:
                    logging.warning(f"YouTube client secret file not found: {secret_str}")
                    return {}
        except json.JSONDecodeError as e:
            logging.error(f"Invalid YouTube client secret JSON: {e}")
            return {}

    # ===== 通知設定 =====
    @property
    def discord_webhook_url(self) -> str:
        """Discord Webhook URL"""
        return os.getenv('DISCORD_WEBHOOK_URL', '')

    # ===== アプリケーション設定 =====
    @property
    def debug(self) -> bool:
        """デバッグモード"""
        return os.getenv('DEBUG', 'false').lower() == 'true'

    @property
    def log_level(self) -> str:
        """ログレベル"""
        return os.getenv('LOG_LEVEL', 'INFO')

    @property
    def max_video_duration_minutes(self) -> int:
        """最大動画長（分）"""
        return int(os.getenv('MAX_VIDEO_DURATION_MINUTES', '40'))

    @property
    def max_concurrent_tts(self) -> int:
        """TTS並列実行数"""
        return int(os.getenv('MAX_CONCURRENT_TTS', '3'))

    @property
    def tts_chunk_size(self) -> int:
        """TTSチャンクサイズ（文字数）"""
        return int(os.getenv('TTS_CHUNK_SIZE', '1500'))

    def _setup_logging(self):
        """ログ設定"""
        log_level = getattr(logging, self.log_level.upper(), logging.INFO)
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('logs/app.log') if os.path.exists('logs') else logging.NullHandler()
            ]
        )

    def _validate_required_vars(self):
        """必須環境変数のチェック"""
        required_vars = [
            'ANTHROPIC_API_KEY',
            'GEMINI_API_KEY',
            'ELEVENLABS_API_KEY',
            'GOOGLE_SHEET_ID',
            'DISCORD_WEBHOOK_URL',
        ]

        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        if missing_vars:
            logging.warning(f"Missing environment variables: {', '.join(missing_vars)}")

    def validate_apis(self) -> dict:
        """API設定の検証結果を返す"""
        results = {}

        # 各APIキーの存在チェック
        apis = {
            'Anthropic': self.anthropic_api_key,
            'Gemini': self.gemini_api_key,
            'ElevenLabs': self.elevenlabs_api_key,
            'Google Sheets': self.google_sheet_id,
            'Google Drive': self.google_drive_folder_id,
            'Discord': self.discord_webhook_url,
        }

        for api_name, api_value in apis.items():
            results[api_name] = {
                'configured': bool(api_value),
                'key_preview': f"{'*' * 10}{api_value[-10:] if len(api_value) > 10 else api_value}" if api_value else None
            }

        # Google認証の詳細チェック
        google_creds = self.google_credentials_json
        results['Google Credentials'] = {
            'configured': bool(google_creds),
            'project_id': google_creds.get('project_id'),
            'client_email': google_creds.get('client_email'),
        }

        # YouTube設定の詳細チェック
        youtube_config = self.youtube_client_secret
        results['YouTube Config'] = {
            'configured': bool(youtube_config),
            'client_id': youtube_config.get('web', {}).get('client_id', '')[:20] + '...' if youtube_config.get('web', {}).get('client_id') else None
        }

        return results

# グローバル設定インスタンス
cfg = Config()

def get_config() -> Config:
    """設定インスタンスを取得"""
    return cfg

def debug_config():
    """設定内容をデバッグ出力"""
    print("=== Configuration Debug ===")
    validation_results = cfg.validate_apis()

    for api_name, result in validation_results.items():
        status = "✓" if result['configured'] else "✗"
        print(f"{status} {api_name}: {'Configured' if result['configured'] else 'Not configured'}")

        if result.get('key_preview'):
            print(f"  Preview: {result['key_preview']}")
        if result.get('project_id'):
            print(f"  Project: {result['project_id']}")
        if result.get('client_email'):
            print(f"  Email: {result['client_email']}")
        if result.get('client_id'):
            print(f"  Client: {result['client_id']}")

    print(f"\nOther settings:")
    print(f"  Debug mode: {cfg.debug}")
    print(f"  Log level: {cfg.log_level}")
    print(f"  Max video duration: {cfg.max_video_duration_minutes} min")
    print(f"  TTS concurrent: {cfg.max_concurrent_tts}")
    print(f"  TTS chunk size: {cfg.tts_chunk_size}")
    print(f"  Gemini keys available: {len(cfg.gemini_api_keys)}")

if __name__ == "__main__":
    debug_config()