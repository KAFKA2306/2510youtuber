import os
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any

# .envファイルを読み込む
load_dotenv()

class SpeakerConfig(BaseModel):
    """話者設定""" 
    name: str
    role: str
    voice_id_env: str
    stability: float = 0.5
    speaking_style: str
    voice_id: str | None = None

    @validator('voice_id', pre=True, always=True)
    def load_voice_id_from_env(cls, v, values):
        return os.getenv(values.get('voice_id_env'))

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
    api_keys: Dict[str, str]

    # 話者設定
    speakers: List[SpeakerConfig]

    # 動画設定
    video: VideoConfig

    # 品質基準
    quality: QualityThresholds

    # CrewAI設定
    crew: CrewConfig
    
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
            "elevenlabs": os.getenv("ELEVENLABS_API_KEY"),
            "youtube": os.getenv("YOUTUBE_CLIENT_SECRET"), # Use client secret
        }
        
        config["api_keys"] = api_keys

        # speakersのvoice_idを環境変数からロード
        if "speakers" in config:
            for speaker in config["speakers"]:
                if "voice_id_env" in speaker:
                    speaker["voice_id"] = os.getenv(speaker["voice_id_env"])

        # pydantic expects the quality field, but yaml has quality_thresholds
        if "quality_thresholds" in config:
            config["quality"] = config.pop("quality_thresholds")

        # For compatibility with old cfg object
        config["use_crewai_script_generation"] = config.get("crew", {}).get("enabled", True)
        config["use_three_stage_quality_check"] = not config.get("crew", {}).get("enabled", True)
        config["max_video_duration_minutes"] = config.get("video", {}).get("max_duration_minutes", 15)

        return cls(**config)

# グローバル設定インスタンス
settings = AppSettings.load()