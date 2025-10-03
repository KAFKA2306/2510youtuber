import os
import yaml
from dotenv import load_dotenv
import json
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional

# .envファイルを読み込む
load_dotenv()

class SpeakerConfig(BaseModel):
    """話者設定""" 
    name: str
    role: str
    voice_id_env: str
    stability: float = 0.5
    speaking_style: str
    similarity_boost: float = 0.75 # 追加
    style: float = 0.1 # 追加
    voice_id: str | None = None

    @validator('voice_id', pre=True, always=True)
    def load_voice_id_from_env(cls, v: Optional[str], values: Dict[str, Any]) -> Optional[str]:
        """環境変数からvoice_idをロード。環境変数が設定されていない場合はNoneを返す。"""
        voice_id_env_key = values.get('voice_id_env')
        if voice_id_env_key:
            return os.getenv(voice_id_env_key)
        return None # 環境変数が設定されていない場合はNoneを返す

class VideoResolution(BaseModel):
    width: int
    height: int

class VideoConfig(BaseModel):
    """動画設定"""
    resolution: VideoResolution
    quality_preset: str = "high"
    max_duration_minutes: int = 40

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

    @classmethod
    def load(cls) -> 'AppSettings':
        """環境変数 + YAMLから設定を読み込み"""
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml")
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
 
        api_keys = {
            "gemini": os.getenv("GEMINI_API_KEY"),
            "perplexity": os.getenv("PERPLEXITY_API_KEY"), # Perplexity APIキーを追加
            "elevenlabs": os.getenv("ELEVENLABS_API_KEY"),
            "youtube": os.getenv("YOUTUBE_CLIENT_SECRET"), # Use client secret
            "google_sheet_id": os.getenv("GOOGLE_SHEET_ID"), # Google Sheet IDを追加
            "google_credentials_json": json.loads(os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")) if os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON") else None, # Google Credentials JSONを追加
        }
        
        # Noneのキーも保持するように変更
        config["api_keys"] = api_keys

        # speakersのvoice_idを環境変数からロード
        speakers_config = []
        if "speakers" in config:
            for speaker_data in config["speakers"]:
                # SpeakerConfigのバリデーターがvoice_id_envを処理するため、ここでは直接設定しない
                speakers_config.append(SpeakerConfig(**speaker_data))
            config["speakers"] = speakers_config
            # tts_voice_configsを生成
            config["tts_voice_configs"] = {s.name: s for s in speakers_config}
        else:
            config["speakers"] = []
            config["tts_voice_configs"] = {}

        # pydantic expects the quality field, but yaml has quality_thresholds
        if "quality_thresholds" in config:
            config["quality"] = QualityThresholds(**config.pop("quality_thresholds"))
        else:
            config["quality"] = QualityThresholds() # デフォルト値を設定

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

        # video.resolution のバリデーションエラー対策
        if "video" in config and "resolution" in config["video"] and isinstance(config["video"]["resolution"], dict):
            config["video"]["resolution"] = VideoResolution(**config["video"]["resolution"])
        elif "video" in config and "resolution" not in config["video"]:
            config["video"]["resolution"] = VideoResolution(width=1920, height=1080) # デフォルト値を設定
        elif "video" not in config:
            config["video"] = VideoConfig(resolution=VideoResolution(width=1920, height=1080))
        
        # qualityフィールドがconfigに存在しない場合のデフォルト値設定
        if "quality" not in config:
            config["quality"] = QualityThresholds()

        # For compatibility with old cfg object
        config["use_crewai_script_generation"] = config.get("crew", {}).get("enabled", True)
        config["use_three_stage_quality_check"] = not config.get("crew", {}).get("enabled", True)
        config["max_video_duration_minutes"] = config.get("video", {}).get("max_duration_minutes", 15)

        return cls(**config)

# グローバル設定インスタンス
settings = AppSettings.load()