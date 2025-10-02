"""設定管理モジュール.

環境変数からAPIキーやその他の設定を読み込み、アプリケーション全体で利用可能にします。
"""

import json
import logging
import os
from typing import List, Optional

from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()


class Config:
    """アプリケーション設定クラス."""

    def __init__(self):
        """Initialize the Config class."""
        self._setup_logging()
        self._validate_required_vars()

    # ===== AI APIs =====
    @property
    def perplexity_api_key(self) -> str:
        """Perplexity API キー."""
        return os.getenv("PERPLEXITY_API_KEY", "")

    @property
    def gemini_api_key(self) -> str:
        """Gemini API キー（メイン）."""
        return os.getenv("GEMINI_API_KEY", "")

    @property
    def gemini_api_keys(self) -> List[str]:
        """Gemini API キーリスト（並列処理用）."""
        keys = [
            os.getenv("GEMINI_API_KEY"),
            os.getenv("GEMINI_API_KEY_2"),
            os.getenv("GEMINI_API_KEY_3"),
        ]
        return [k for k in keys if k]

    @property
    def elevenlabs_api_key(self) -> str:
        """ElevenLabs API キー."""
        return os.getenv("ELEVENLABS_API_KEY", "")

    # ===== Stock Footage APIs (FREE) =====
    @property
    def pexels_api_key(self) -> str:
        """Pexels API キー（無料、無制限）- https://www.pexels.com/api/"""
        return os.getenv("PEXELS_API_KEY", "")

    @property
    def pixabay_api_key(self) -> str:
        """Pixabay API キー（無料、無制限）- https://pixabay.com/api/docs/"""
        return os.getenv("PIXABAY_API_KEY", "")

    # ===== Google Services =====
    @property
    def google_credentials_json(self) -> dict:
        """Google認証情報（JSON）- For Drive/Sheets only, NOT for Vertex AI."""
        creds_str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        if not creds_str:
            logging.info("GOOGLE_APPLICATION_CREDENTIALS not set (this is OK, prevents Vertex AI billing errors)")
            return {}

        try:
            if creds_str.startswith("{"):
                # JSON文字列として解析
                return json.loads(creds_str)
            else:
                # ファイルパスとして扱う
                if os.path.exists(creds_str):
                    with open(creds_str, "r") as f:
                        return json.load(f)
                else:
                    logging.warning(f"Google credentials file not found: {creds_str}")
                    return {}
        except json.JSONDecodeError as e:
            logging.error(f"Invalid Google credentials JSON: {e}")
            return {}

    @property
    def google_sheet_id(self) -> str:
        """Google Sheets ID."""
        return os.getenv("GOOGLE_SHEET_ID", "")

    @property
    def google_drive_folder_id(self) -> str:
        """Google Drive フォルダID."""
        return os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")

    @property
    def youtube_client_secret(self) -> Optional[dict]:
        """YouTube API クライアント設定."""
        secret_str = os.getenv("YOUTUBE_CLIENT_SECRET")
        if not secret_str:
            return None

        try:
            if secret_str.startswith("{"):
                return json.loads(secret_str)
            else:
                if os.path.exists(secret_str):
                    with open(secret_str, "r") as f:
                        return json.load(f)
                else:
                    logging.warning(f"YouTube client secret file not found: {secret_str}")
                    return None
        except json.JSONDecodeError as e:
            logging.error(f"Invalid YouTube client secret JSON: {e}")
            return None

    # ===== 通知設定 =====
    @property
    def discord_webhook_url(self) -> str:
        """Discord Webhook URL."""
        return os.getenv("DISCORD_WEBHOOK_URL", "")

    # ===== アプリケーション設定 =====
    @property
    def debug(self) -> bool:
        """デバッグモード."""
        return os.getenv("DEBUG", "false").lower() == "true"

    @property
    def log_level(self) -> str:
        """ログレベル."""
        return os.getenv("LOG_LEVEL", "INFO")

    # ===== 動画・字幕設定 =====
    @property
    def video_resolution(self) -> tuple:
        """動画解像度 (width, height)."""
        width = int(os.getenv("VIDEO_WIDTH", "1920"))
        height = int(os.getenv("VIDEO_HEIGHT", "1080"))
        return (width, height)

    @property
    def thumbnail_resolution(self) -> tuple:
        """サムネイル解像度 (width, height)."""
        width = int(os.getenv("THUMBNAIL_WIDTH", "1280"))
        height = int(os.getenv("THUMBNAIL_HEIGHT", "720"))
        return (width, height)

    @property
    def subtitle_font_size(self) -> int:
        """字幕フォントサイズ."""
        return int(os.getenv("SUBTITLE_FONT_SIZE", "48"))

    @property
    def subtitle_color(self) -> str:
        """字幕カラー (ASS形式: &H00BBGGRR)."""
        return os.getenv("SUBTITLE_COLOR", "&H00FFFF00")  # 黄色

    @property
    def subtitle_outline_width(self) -> int:
        """字幕アウトライン幅."""
        return int(os.getenv("SUBTITLE_OUTLINE", "5"))

    @property
    def subtitle_margin_v(self) -> int:
        """字幕下部マージン."""
        return int(os.getenv("SUBTITLE_MARGIN_V", "100"))

    @property
    def subtitle_margin_h(self) -> int:
        """字幕左右マージン."""
        return int(os.getenv("SUBTITLE_MARGIN_H", "80"))

    @property
    def max_video_duration_minutes(self) -> int:
        """最大動画長（分）."""
        return int(os.getenv("MAX_VIDEO_DURATION_MINUTES", "40"))

    @property
    def max_concurrent_tts(self) -> int:
        """TTS並列実行数."""
        return int(os.getenv("MAX_CONCURRENT_TTS", "3"))

    @property
    def tts_chunk_size(self) -> int:
        """TTSチャンクサイズ（文字数）."""
        return int(os.getenv("TTS_CHUNK_SIZE", "1500"))

    @property
    def tts_voice_configs(self) -> dict:
        """TTS音声設定（話者ごとの設定）."""
        return {
            "田中": {
                "voice_id": os.getenv("TTS_VOICE_TANAKA", "8PfKHL4nZToWC3pbz9U9"),
                "stability": float(os.getenv("TTS_VOICE_TANAKA_STABILITY", "0.5")),
                "similarity_boost": float(os.getenv("TTS_VOICE_TANAKA_SIMILARITY", "0.75")),
                "style": float(os.getenv("TTS_VOICE_TANAKA_STYLE", "0.1")),
                "use_speaker_boost": os.getenv("TTS_VOICE_TANAKA_BOOST", "true").lower() == "true",
            },
            "鈴木": {
                "voice_id": os.getenv("TTS_VOICE_SUZUKI", "8PfKHL4nZToWC3pbz9U9"),
                "stability": float(os.getenv("TTS_VOICE_SUZUKI_STABILITY", "0.4")),
                "similarity_boost": float(os.getenv("TTS_VOICE_SUZUKI_SIMILARITY", "0.8")),
                "style": float(os.getenv("TTS_VOICE_SUZUKI_STYLE", "0.2")),
                "use_speaker_boost": os.getenv("TTS_VOICE_SUZUKI_BOOST", "true").lower() == "true",
            },
            "ナレーター": {
                "voice_id": os.getenv("TTS_VOICE_NARRATOR", "pNInz6obpgDQGcFmaJgB"),
                "stability": float(os.getenv("TTS_VOICE_NARRATOR_STABILITY", "0.6")),
                "similarity_boost": float(os.getenv("TTS_VOICE_NARRATOR_SIMILARITY", "0.7")),
                "style": float(os.getenv("TTS_VOICE_NARRATOR_STYLE", "0.0")),
                "use_speaker_boost": os.getenv("TTS_VOICE_NARRATOR_BOOST", "true").lower() == "true",
            },
        }

    @property
    def tts_voicevox_port(self) -> int:
        """VOICEVOX Nemoのポート番号."""
        return int(os.getenv("TTS_VOICEVOX_PORT", "50121"))

    @property
    def tts_voicevox_speaker(self) -> int:
        """VOICEVOX話者ID."""
        return int(os.getenv("TTS_VOICEVOX_SPEAKER", "1"))

    @property
    def ffmpeg_path(self) -> str:
        """FFmpeg実行パス."""
        return os.getenv("FFMPEG_PATH", "ffmpeg")

    @property
    def video_quality(self) -> str:
        """動画品質."""
        return os.getenv("VIDEO_QUALITY", "high")

    @property
    def video_quality_presets(self) -> dict:
        """動画品質プリセット設定."""
        return {
            "low": {"preset": "fast", "crf": 28},
            "medium": {"preset": "medium", "crf": 23},
            "high": {"preset": "slow", "crf": 18},
            "ultra": {"preset": "veryslow", "crf": 15},
        }

    @property
    def background_colors(self) -> dict:
        """背景カラースキーム."""
        return {
            "daily": {
                "base": (10, 20, 35),
                "gradient_top": (10, 20, 35),
                "gradient_mid": (15, 45, 70),
                "gradient_bottom": (25, 60, 85),
                "accent_primary": (0, 120, 215),
                "accent_gold": (255, 215, 0),
            },
            "special": {
                "base": (30, 5, 5),
                "gradient_top": (30, 5, 5),
                "gradient_mid": (50, 15, 15),
                "gradient_bottom": (80, 20, 20),
                "accent_primary": (255, 50, 50),
                "accent_gold": (255, 215, 0),
            },
            "breaking": {
                "base": (5, 30, 5),
                "gradient_top": (5, 30, 5),
                "gradient_mid": (15, 60, 15),
                "gradient_bottom": (20, 80, 20),
                "accent_primary": (0, 180, 80),
                "accent_gold": (255, 193, 7),
            },
        }

    @property
    def local_output_dir(self) -> str:
        """ローカル出力ディレクトリ."""
        return os.getenv("LOCAL_OUTPUT_DIR", "output")

    @property
    def use_crewai_script_generation(self) -> bool:
        """CrewAI WOW Script Creation Flowを使用するか."""
        return os.getenv("USE_CREWAI_SCRIPT_GENERATION", "true").lower() == "true"

    @property
    def use_three_stage_quality_check(self) -> bool:
        """3段階品質チェックを使用するか（CrewAI無効時のみ）."""
        return os.getenv("USE_THREE_STAGE_QUALITY_CHECK", "true").lower() == "true"

    @property
    def quality_check_threshold(self) -> float:
        """品質チェックの合格基準（10点満点）."""
        return float(os.getenv("QUALITY_CHECK_THRESHOLD", "7.0"))

    @property
    def use_japanese_quality_check(self) -> bool:
        """日本語品質チェックを使用するか（英語混入の検出と修正）."""
        return os.getenv("USE_JAPANESE_QUALITY_CHECK", "true").lower() == "true"

    @property
    def japanese_purity_threshold(self) -> float:
        """日本語純度の合格基準（0-100）."""
        return float(os.getenv("JAPANESE_PURITY_THRESHOLD", "90.0"))

    @property
    def save_local_backup(self) -> bool:
        """ローカルバックアップを保存."""
        return os.getenv("SAVE_LOCAL_BACKUP", "true").lower() == "true"

    # ===== Stock Footage Settings =====
    @property
    def enable_stock_footage(self) -> bool:
        """無料ストック映像を使用するか（Pexels/Pixabay）."""
        return os.getenv("ENABLE_STOCK_FOOTAGE", "true").lower() == "true"

    @property
    def stock_footage_clips_per_video(self) -> int:
        """動画あたりのストック映像クリップ数."""
        return int(os.getenv("STOCK_CLIPS_PER_VIDEO", "5"))

    def _setup_logging(self):
        """ログ設定."""
        log_level = getattr(logging, self.log_level.upper(), logging.INFO)
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler("logs/app.log") if os.path.exists("logs") else logging.NullHandler(),
            ],
        )

    def _validate_required_vars(self):
        """必須環境変数のチェック."""
        required_vars = [
            "PERPLEXITY_API_KEY",
            "GEMINI_API_KEY",
            "ELEVENLABS_API_KEY",
            "GOOGLE_SHEET_ID",
            "DISCORD_WEBHOOK_URL",
        ]

        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        if missing_vars:
            logging.warning(f"Missing environment variables: {', '.join(missing_vars)}")

    def validate_apis(self) -> dict:
        """API設定の検証結果を返す."""
        results = {}

        # 各APIキーの存在チェック
        apis = {
            "Perplexity": self.perplexity_api_key,
            "Gemini": self.gemini_api_key,
            "ElevenLabs": self.elevenlabs_api_key,
            "Google Sheets": self.google_sheet_id,
            "Google Drive": self.google_drive_folder_id,
            "Discord": self.discord_webhook_url,
        }

        for api_name, api_value in apis.items():
            results[api_name] = {
                "configured": bool(api_value),
                "key_preview": f"{'*' * 10}{api_value[-10:] if len(api_value) > 10 else api_value}"
                if api_value
                else None,
            }

        # Google認証の詳細チェック
        google_creds = self.google_credentials_json
        results["Google Credentials"] = {
            "configured": bool(google_creds),
            "project_id": google_creds.get("project_id"),
            "client_email": google_creds.get("client_email"),
        }

        # YouTube設定の詳細チェック
        youtube_config = self.youtube_client_secret
        results["YouTube Config"] = {
            "configured": bool(youtube_config),
            "client_id": youtube_config.get("web", {}).get("client_id", "")[:20] + "..."
            if youtube_config.get("web", {}).get("client_id")
            else None,
        }

        return results


# グローバル設定インスタンス
cfg = Config()


def get_config() -> Config:
    """設定インスタンスを取得."""
    return cfg


def debug_config():
    """設定内容をデバッグ出力."""
    print("=== Configuration Debug ===")
    validation_results = cfg.validate_apis()

    for api_name, result in validation_results.items():
        status = "✓" if result["configured"] else "✗"
        print(f"{status} {api_name}: {'Configured' if result['configured'] else 'Not configured'}")

        if result.get("key_preview"):
            print(f"  Preview: {result['key_preview']}")
        if result.get("project_id"):
            print(f"  Project: {result['project_id']}")
        if result.get("client_email"):
            print(f"  Email: {result['client_email']}")
        if result.get("client_id"):
            print(f"  Client: {result['client_id']}")

    print("\nOther settings:")
    print(f"  Debug mode: {cfg.debug}")
    print(f"  Log level: {cfg.log_level}")
    print(f"  Max video duration: {cfg.max_video_duration_minutes} min")
    print(f"  TTS concurrent: {cfg.max_concurrent_tts}")
    print(f"  TTS chunk size: {cfg.tts_chunk_size}")
    print(f"  Gemini keys available: {len(cfg.gemini_api_keys)}")


if __name__ == "__main__":
    debug_config()
