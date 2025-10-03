import json
import os
from typing import Any, Dict, List, Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, validator

# .envファイルを読み込む
load_dotenv()


class SpeakerConfig(BaseModel):
    """話者設定"""

    name: str
    role: str
    voice_id_env: str
    stability: float = 0.5
    speaking_style: str
    similarity_boost: float = 0.75  # 追加
    style: float = 0.1  # 追加
    voice_id: str | None = None

    @validator("voice_id", pre=True, always=True)
    def load_voice_id_from_env(cls, v: Optional[str], values: Dict[str, Any]) -> Optional[str]:
        """環境変数からvoice_idをロード。環境変数が設定されていない場合はNoneを返す。"""
        voice_id_env_key = values.get("voice_id_env")
        if voice_id_env_key:
            return os.getenv(voice_id_env_key)
        return None  # 環境変数が設定されていない場合はNoneを返す


class VideoResolution(BaseModel):
    width: int
    height: int


class VideoConfig(BaseModel):
    """動画設定"""

    resolution: VideoResolution
    quality_preset: str = "high"
    max_duration_minutes: int = 40


class VideoReviewConfig(BaseModel):
    """生成済み動画をAIがレビューするための設定"""

    enabled: bool = True
    screenshot_interval_seconds: int = 60
    max_screenshots: int = 15
    output_dir: str = "output/video_reviews"
    model: str = "gemini-2.5-pro"
    temperature: float = 0.4
    max_output_tokens: int = 2048
    store_feedback: bool = True


class QualityThresholds(BaseModel):
    """品質基準"""

    wow_score_min: float = 8.0
    japanese_purity_min: float = 95.0
    retention_prediction_min: float = 50.0
    surprise_points_min: int = 5
    emotion_peaks_min: int = 5


class CrewConfig(BaseModel):
    """CrewAI設定"""

    enabled: bool = True
    max_quality_iterations: int = 2
    parallel_analysis: bool = True
    verbose: bool = False


class MediaQAGatingConfig(BaseModel):
    """QAゲートの挙動設定"""

    enforce: bool = True
    skip_modes: List[str] = Field(default_factory=lambda: ["test"])
    fail_on_missing_inputs: bool = True
    retry_attempts: int = 1
    retry_start_step: str = "script_generation"


class AudioQAConfig(BaseModel):
    """音声品質チェック設定"""

    enabled: bool = True
    peak_dbfs_max: float = -1.0
    rms_dbfs_min: float = -24.0
    rms_dbfs_max: float = -10.0
    max_silence_seconds: float = 1.5


class VideoQAConfig(BaseModel):
    """動画品質チェック設定"""

    enabled: bool = True
    expected_resolution: VideoResolution = Field(
        default_factory=lambda: VideoResolution(width=1920, height=1080)
    )
    min_fps: float = 24.0
    max_fps: float = 61.0
    min_bitrate_kbps: int = 3200


class SubtitleQAConfig(BaseModel):
    """字幕品質チェック設定"""

    enabled: bool = True
    min_line_coverage: float = 0.9
    max_timing_gap_seconds: float = 1.5


class MediaQAConfig(BaseModel):
    """メディアQA統合設定"""

    enabled: bool = True
    report_dir: str = "data/qa_reports"
    gating: MediaQAGatingConfig = Field(default_factory=MediaQAGatingConfig)
    audio: AudioQAConfig = Field(default_factory=AudioQAConfig)
    video: VideoQAConfig = Field(default_factory=VideoQAConfig)
    subtitles: SubtitleQAConfig = Field(default_factory=SubtitleQAConfig)


class AppSettings(BaseModel):
    """アプリケーション統合設定"""

    # API設定
    api_keys: Dict[str, Optional[str]]

    # 話者設定
    speakers: List[SpeakerConfig]

    # 動画設定
    video: VideoConfig

    # 品質基準
    quality: QualityThresholds

    # CrewAI設定
    crew: CrewConfig

    # TTS設定
    max_concurrent_tts: int = 4
    tts_chunk_size: int = 500
    tts_voicevox_port: int = 50121
    tts_voicevox_speaker: int = 0

    # 字幕設定
    subtitle_font_size: int = 48
    subtitle_outline_width: int = 2

    # ストック映像設定
    pexels_api_key: Optional[str] = None
    pixabay_api_key: Optional[str] = None
    ffmpeg_path: str = "ffmpeg"
    enable_stock_footage: bool = False
    stock_footage_clips_per_video: int = 5

    # TTS話者設定 (tts_voice_configs)
    tts_voice_configs: Dict[str, SpeakerConfig] = Field(default_factory=dict)

    use_crewai_script_generation: bool = True
    use_three_stage_quality_check: bool = True
    max_video_duration_minutes: int = 15
    video_review: VideoReviewConfig = Field(default_factory=VideoReviewConfig)
    media_quality: MediaQAConfig = Field(default_factory=MediaQAConfig)

    # Google Drive/Sheets settings (for backward compatibility)
    google_sheet_id: Optional[str] = None
    google_credentials_json: Optional[Dict[str, Any]] = None
    google_drive_folder_id: Optional[str] = None
    discord_webhook_url: Optional[str] = None
    gemini_daily_quota_limit: int = 0
    newsapi_key: Optional[str] = None
    save_local_backup: bool = False

    # Legacy properties for backward compatibility
    @property
    def gemini_api_key(self) -> Optional[str]:
        """Get primary Gemini API key"""
        return self.api_keys.get("gemini")

    @property
    def gemini_api_keys(self) -> List[str]:
        """Get all Gemini API keys (primary + rotation keys)"""
        keys = []
        if self.api_keys.get("gemini"):
            keys.append(self.api_keys["gemini"])
        for i in range(2, 10):
            key = os.getenv(f"GEMINI_API_KEY_{i}")
            if key:
                keys.append(key)
        return keys

    @property
    def perplexity_api_key(self) -> Optional[str]:
        """Get Perplexity API key"""
        return self.api_keys.get("perplexity")

    @property
    def elevenlabs_api_key(self) -> Optional[str]:
        """Get ElevenLabs API key"""
        return self.api_keys.get("elevenlabs")

    @property
    def youtube_client_secret(self) -> Optional[str]:
        """Get YouTube client secret"""
        return self.api_keys.get("youtube")

    @property
    def video_quality_presets(self) -> Dict[str, Any]:
        """Get video quality presets for backward compatibility"""
        return {
            "low": {"c:v": "libx264", "preset": "fast", "crf": "28", "b:v": "1000k"},
            "medium": {"c:v": "libx264", "preset": "medium", "crf": "23", "b:v": "2500k"},
            "high": {"c:v": "libx264", "preset": "slow", "crf": "20", "b:v": "5000k"},
            "ultra": {"c:v": "libx264", "preset": "veryslow", "crf": "18", "b:v": "8000k"},
        }

    @classmethod
    def load(cls) -> "AppSettings":
        """環境変数 + YAMLから設定を読み込み"""
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml")
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        api_keys = {
            "gemini": os.getenv("GEMINI_API_KEY"),
            "perplexity": os.getenv("PERPLEXITY_API_KEY"),  # Perplexity APIキーを追加
            "elevenlabs": os.getenv("ELEVENLABS_API_KEY"),
            "youtube": os.getenv("YOUTUBE_CLIENT_SECRET"),  # Use client secret
            "google_sheet_id": os.getenv("GOOGLE_SHEET_ID"),  # Google Sheet IDを追加
            "google_credentials_json": json.loads(os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON"))
            if os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
            else None,  # Google Credentials JSONを追加
        }

        # Noneのキーも保持するように変更
        config["api_keys"] = api_keys

        # speakersのvoice_idを環境変数からロード
        speakers_config: List[SpeakerConfig] = []
        if "speakers" in config:
            for speaker_data in config["speakers"]:
                # SpeakerConfigのバリデーターがvoice_id_envを処理するため、ここでは直接設定しない
                speakers_config.append(SpeakerConfig(**speaker_data))
        else:
            config["speakers"] = []

        config["speakers"] = speakers_config
        config["tts_voice_configs"] = {s.name: s for s in speakers_config}

        # 動画レビュー設定
        if "video_review" in config:
            config["video_review"] = VideoReviewConfig(**config["video_review"])
        else:
            config["video_review"] = VideoReviewConfig()

        # メディア品質設定
        if "media_quality" in config:
            config["media_quality"] = MediaQAConfig(**config["media_quality"])
        else:
            config["media_quality"] = MediaQAConfig()

        # pydantic expects the quality field, but yaml has quality_thresholds
        if "quality_thresholds" in config:
            config["quality"] = QualityThresholds(**config.pop("quality_thresholds"))
        else:
            config["quality"] = QualityThresholds()  # デフォルト値を設定

        # TTS関連の設定をトップレベルにマッピング
        if "tts" in config:
            config["max_concurrent_tts"] = config["tts"].get("max_concurrent", 4)
            config["tts_chunk_size"] = config["tts"].get("chunk_size", 500)
            config["tts_voicevox_port"] = config["tts"].get("voicevox_port", 50121)
            config["tts_voicevox_speaker"] = config["tts"].get("voicevox_speaker", 0)

        # 字幕関連の設定をトップレベルにマッピング
        if "subtitle" in config:
            config["subtitle_font_size"] = config["subtitle"].get("font_size", 48)
            config["subtitle_outline_width"] = config["subtitle"].get("outline_width", 2)

        # ストック映像関連の設定をトップレベルにマッピング
        if "stock_footage" in config:
            config["enable_stock_footage"] = config["stock_footage"].get("enabled", False)
            config["stock_footage_clips_per_video"] = config["stock_footage"].get("clips_per_video", 5)
            config["ffmpeg_path"] = config["stock_footage"].get("ffmpeg_path", "ffmpeg")

        enable_stock_env = os.getenv("ENABLE_STOCK_FOOTAGE")
        if enable_stock_env is not None:
            config["enable_stock_footage"] = enable_stock_env.strip().lower() in {"1", "true", "yes", "on"}

        stock_clips_env = os.getenv("STOCK_CLIPS_PER_VIDEO")
        if stock_clips_env is not None:
            try:
                config["stock_footage_clips_per_video"] = max(1, int(stock_clips_env))
            except ValueError:
                pass

        # video.resolution のバリデーションエラー対策
        if "video" in config and "resolution" in config["video"] and isinstance(config["video"]["resolution"], dict):
            config["video"]["resolution"] = VideoResolution(**config["video"]["resolution"])
        elif "video" in config and "resolution" not in config["video"]:
            config["video"]["resolution"] = VideoResolution(width=1920, height=1080)  # デフォルト値を設定
        elif "video" not in config:
            config["video"] = VideoConfig(resolution=VideoResolution(width=1920, height=1080))

        # qualityフィールドがconfigに存在しない場合のデフォルト値設定
        if "quality" not in config:
            config["quality"] = QualityThresholds()

        # For compatibility with old cfg object
        config["use_crewai_script_generation"] = config.get("crew", {}).get("enabled", True)
        config["use_three_stage_quality_check"] = not config.get("crew", {}).get("enabled", True)
        config["max_video_duration_minutes"] = config.get("video", {}).get("max_duration_minutes", 15)

        # Load Google-related settings from environment variables and api_keys
        config["google_sheet_id"] = os.getenv("GOOGLE_SHEET_ID")
        config["google_drive_folder_id"] = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
        config["discord_webhook_url"] = os.getenv("DISCORD_WEBHOOK_URL")

        # NewsAPI fallback key
        config["newsapi_key"] = os.getenv("NEWSAPI_API_KEY")

        # Load gemini_daily_quota_limit from config.yaml
        if "api" in config:
            config["gemini_daily_quota_limit"] = config["api"].get("gemini_daily_quota_limit", 0)

        # Load save_local_backup from config.yaml
        if "backup" in config:
            config["save_local_backup"] = config["backup"].get("save_local_backup", False)

        # Load Google credentials from file or JSON string
        google_creds_env = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if google_creds_env:
            if os.path.exists(google_creds_env):
                with open(google_creds_env, "r") as f:
                    config["google_credentials_json"] = json.load(f)
            else:
                try:
                    config["google_credentials_json"] = json.loads(google_creds_env)
                except json.JSONDecodeError:
                    config["google_credentials_json"] = None
        else:
            # Fallback to api_keys if available
            config["google_credentials_json"] = api_keys.get("google_credentials_json")

        return cls(**config)


# グローバル設定インスタンス
settings = AppSettings.load()
