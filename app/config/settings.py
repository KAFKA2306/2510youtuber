"""統合設定管理

環境変数とYAMLファイルから設定を読み込み、
Pydanticモデルで型安全性を確保します。
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv

# 環境変数読み込み
load_dotenv()


class SpeakerConfig(BaseModel):
    """話者設定"""
    name: str
    role: str
    voice_id_env: str  # 環境変数名
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    speaking_style: str = ""
    speaking_pattern: str = ""

    @property
    def voice_id(self) -> str:
        """環境変数から実際のvoice_idを取得"""
        return os.getenv(self.voice_id_env, "")


class VideoConfig(BaseModel):
    """動画設定"""
    resolution: Dict[str, int]
    quality_preset: str = "high"
    max_duration_minutes: int = 40
    target_duration_minutes: int = 8

    @property
    def resolution_tuple(self) -> tuple[int, int]:
        """解像度をタプルで取得"""
        return (self.resolution['width'], self.resolution['height'])


class SubtitleConfig(BaseModel):
    """字幕設定"""
    font_size: int = 48
    color: str = "&H00FFFF00"
    outline_width: int = 5
    margin_v: int = 100
    margin_h: int = 80


class ThumbnailConfig(BaseModel):
    """サムネイル設定"""
    resolution: Dict[str, int]

    @property
    def resolution_tuple(self) -> tuple[int, int]:
        return (self.resolution['width'], self.resolution['height'])


class QualityThresholds(BaseModel):
    """品質基準"""
    wow_score_min: float = 8.0
    wow_score_excellent: float = 9.0
    japanese_purity_min: float = 95.0
    japanese_purity_excellent: float = 98.0
    retention_prediction_min: float = 50.0
    retention_first_minute_min: float = 70.0

    # WOW要素の最小数
    surprise_points_min: int = 5
    emotion_peaks_min: int = 5
    curiosity_gaps_min: int = 3
    visual_instructions_min: int = 15
    concrete_numbers_min: int = 10
    viewer_questions_min: int = 3


class AgentConfig(BaseModel):
    """エージェント設定"""
    model: str = "gemini-2.5-flash"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout_seconds: int = 120


class RetentionPredictorConfig(BaseModel):
    """保持率予測設定"""
    interval_seconds: int = 30
    targets: Dict[str, int]


class CrewConfig(BaseModel):
    """CrewAI設定"""
    enabled: bool = True
    max_quality_iterations: int = 2
    parallel_analysis: bool = True
    verbose: bool = False
    agents: Dict[str, AgentConfig]
    retention_predictor: RetentionPredictorConfig


class YouTubeOptimization(BaseModel):
    """YouTube最適化ルール"""
    first_8_seconds: Dict[str, Any]
    pattern_interrupt: Dict[str, Any]
    prep_method: Dict[str, Any]
    dialogue_rhythm: Dict[str, Any]


class PromptsConfig(BaseModel):
    """プロンプト設定"""
    directory: str = "app/config/prompts"
    files: Dict[str, str]


class TTSConfig(BaseModel):
    """TTS設定"""
    max_concurrent: int = 3
    chunk_size: int = 1500
    voicevox: Dict[str, Any] = Field(default_factory=dict)


class DebugConfig(BaseModel):
    """デバッグ設定"""
    enabled: bool = False
    log_level: str = "INFO"
    save_intermediate_files: bool = False
    save_prompts: bool = True


class BackupConfig(BaseModel):
    """バックアップ設定"""
    save_local: bool = True
    output_dir: str = "output"


class AppSettings(BaseModel):
    """アプリケーション統合設定"""

    # 各セクションの設定
    speakers: List[SpeakerConfig]
    video: VideoConfig
    subtitle: SubtitleConfig
    thumbnail: ThumbnailConfig
    quality_thresholds: QualityThresholds
    crew: CrewConfig
    youtube_optimization: YouTubeOptimization
    prompts: PromptsConfig
    tts: TTSConfig
    debug: DebugConfig
    backup: BackupConfig

    # API Keys（環境変数から取得）
    _api_keys: Dict[str, str] = {}

    def __init__(self, **data):
        super().__init__(**data)
        # API Keysを環境変数から読み込み
        self._api_keys = {
            'perplexity': os.getenv('PERPLEXITY_API_KEY', ''),
            'gemini': os.getenv('GEMINI_API_KEY', ''),
            'gemini_2': os.getenv('GEMINI_API_KEY_2', ''),
            'gemini_3': os.getenv('GEMINI_API_KEY_3', ''),
            'elevenlabs': os.getenv('ELEVENLABS_API_KEY', ''),
        }

    @property
    def api_keys(self) -> Dict[str, str]:
        """API Keys取得"""
        return self._api_keys

    @property
    def gemini_api_keys(self) -> List[str]:
        """Gemini API Keysリスト（並列処理用）"""
        keys = [
            self._api_keys.get('gemini', ''),
            self._api_keys.get('gemini_2', ''),
            self._api_keys.get('gemini_3', ''),
        ]
        return [k for k in keys if k]

    # Google Services
    @property
    def google_sheet_id(self) -> str:
        return os.getenv('GOOGLE_SHEET_ID', '')

    @property
    def google_drive_folder_id(self) -> str:
        return os.getenv('GOOGLE_DRIVE_FOLDER_ID', '')

    @property
    def discord_webhook_url(self) -> str:
        return os.getenv('DISCORD_WEBHOOK_URL', '')

    def get_speaker_config(self, name: str) -> Optional[SpeakerConfig]:
        """話者設定を取得"""
        for speaker in self.speakers:
            if speaker.name == name:
                return speaker
        return None

    def get_agent_config(self, agent_name: str) -> Optional[AgentConfig]:
        """エージェント設定を取得"""
        return self.crew.agents.get(agent_name)

    @classmethod
    def load_from_yaml(cls, yaml_path: str = "config.yaml") -> 'AppSettings':
        """YAMLファイルから設定を読み込み"""
        yaml_file = Path(yaml_path)
        if not yaml_file.exists():
            raise FileNotFoundError(f"Config file not found: {yaml_path}")

        with open(yaml_file, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)

        return cls(**config_data)

    class Config:
        arbitrary_types_allowed = True


# グローバル設定インスタンス
def _load_settings() -> AppSettings:
    """設定を読み込み"""
    try:
        return AppSettings.load_from_yaml()
    except FileNotFoundError:
        # config.yamlが見つからない場合、既存のconfig.pyから移行
        print("Warning: config.yaml not found, using environment variables only")
        # 最小限の設定でインスタンス化
        minimal_config = {
            "speakers": [],
            "video": {"resolution": {"width": 1920, "height": 1080}},
            "subtitle": {},
            "thumbnail": {"resolution": {"width": 1280, "height": 720}},
            "quality_thresholds": {},
            "crew": {
                "agents": {},
                "retention_predictor": {"interval_seconds": 30, "targets": {}}
            },
            "youtube_optimization": {
                "first_8_seconds": {},
                "pattern_interrupt": {},
                "prep_method": {},
                "dialogue_rhythm": {}
            },
            "prompts": {"files": {}},
            "tts": {},
            "debug": {},
            "backup": {}
        }
        return AppSettings(**minimal_config)


settings = _load_settings()


def get_settings() -> AppSettings:
    """設定インスタンスを取得"""
    return settings
