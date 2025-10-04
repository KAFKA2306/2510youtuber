import json
import os
from typing import Any, Dict, List, Optional

import yaml
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel

from app.config.paths import ProjectPaths

# .envファイルを読み込む
load_dotenv(ProjectPaths.DOTENV_FILE)


class PromptManager:
    """プロンプトテンプレート管理クラス"""

    def __init__(self, prompt_config: Dict[str, Any]):
        self.prompt_config = prompt_config
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.env = self._setup_jinja_env()

    def _setup_jinja_env(self):
        """Jinja2環境をセットアップ"""
        template_dirs = [
            os.path.join(self.base_dir, "prompts"),
            os.path.join(self.base_dir, "..", "config_prompts", "prompts"),  # 既存のプロンプトディレクトリ
        ]
        # config.yamlで指定されたディレクトリも追加
        if "directory" in self.prompt_config:
            template_dirs.append(os.path.join(self.base_dir, "..", "..", self.prompt_config["directory"]))

        loader = FileSystemLoader(template_dirs)
        return Environment(
            loader=loader, autoescape=select_autoescape(["html", "xml"]), trim_blocks=True, lstrip_blocks=True
        )

    def get_prompt_template(self, template_name: str) -> str:
        """指定された名前のプロンプトテンプレートを読み込む"""
        # config.yamlのfilesセクションからファイル名を解決
        file_name = self.prompt_config.get("files", {}).get(template_name, f"{template_name}.yaml")

        # YAMLファイルを読み込み、Jinja2テンプレートとして返す
        template_path = os.path.join("prompts", file_name)  # デフォルトのpromptsサブディレクトリを想定

        # 直接ファイル名が指定された場合も考慮
        if not os.path.exists(os.path.join(self.env.loader.searchpath[0], template_path)):
            template_path = file_name

        template = self.env.get_template(template_path)
        return template.render()  # テンプレート自体を文字列として返す

    def render_prompt(self, template_name: str, data: Dict[str, Any]) -> str:
        """プロンプトテンプレートをレンダリングする"""
        template_content = self.get_prompt_template(template_name)
        template = self.env.from_string(template_content)
        return template.render(**data)


class SpeakerConfig(BaseModel):
    """話者設定"""

    name: str
    role: str
    voice_id: Optional[str] = "default"
    stability: float = 0.5
    speaking_style: str


class VideoConfig(BaseModel):
    """動画設定"""

    resolution: tuple[int, int] = (1920, 1080)
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

    model_config = {"arbitrary_types_allowed": True}

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
    discord_webhook_url: Optional[str] = None
    google_credentials_json: Optional[Dict[str, Any]] = None  # Google Sheets認証情報
    google_sheet_id: Optional[str] = None  # Google Sheet ID

    # プロンプトマネージャーインスタンス
    prompt_manager: PromptManager

    @classmethod
    def load(cls) -> "AppSettings":
        """環境変数 + YAMLから設定を読み込み"""
        config_path = ProjectPaths.CONFIG_YAML
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        api_keys = {
            "gemini": os.getenv("GEMINI_API_KEY"),
            "elevenlabs": os.getenv("ELEVENLABS_API_KEY"),
            "youtube": os.getenv("YOUTUBE_CLIENT_SECRET"),
        }

        config["api_keys"] = api_keys

        # Handle speakers voice_id_env
        for speaker in config.get("speakers", []):
            if "voice_id_env" in speaker:
                env_var_name = speaker["voice_id_env"]
                speaker["voice_id"] = os.getenv(env_var_name)
                del speaker["voice_id_env"]

        # Handle video resolution
        if "video" in config and "resolution" in config["video"]:
            res = config["video"]["resolution"]
            if isinstance(res, dict) and "width" in res and "height" in res:
                config["video"]["resolution"] = (res["width"], res["height"])

        # Map quality_thresholds to quality
        if "quality_thresholds" in config:
            config["quality"] = config["quality_thresholds"]
            del config["quality_thresholds"]

        # Add discord_webhook_url from environment variable
        config["discord_webhook_url"] = os.getenv("DISCORD_WEBHOOK_URL")

        # Add google_sheet_id from environment variable
        config["google_sheet_id"] = os.getenv("GOOGLE_SHEET_ID")

        # Google Credentials JSON
        google_creds_env = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if google_creds_env:
            google_creds_env = google_creds_env.strip()
            if google_creds_env.startswith("{"):
                try:
                    config["google_credentials_json"] = json.loads(google_creds_env)
                except json.JSONDecodeError:
                    pass  # Invalid JSON, will be handled by Pydantic if field is not Optional
            else:
                resolved = ProjectPaths.resolve_relative(google_creds_env)
                if resolved.exists():
                    with open(resolved, "r", encoding="utf-8") as f:
                        config["google_credentials_json"] = json.load(f)

        if "google_credentials_json" not in config or not config["google_credentials_json"]:
            default_creds = ProjectPaths.resolve_google_credentials(None)
            if default_creds and default_creds.exists():
                with open(default_creds, "r", encoding="utf-8") as f:
                    config["google_credentials_json"] = json.load(f)

        # PromptManagerのインスタンスを生成
        config["prompt_manager"] = PromptManager(config.get("prompts", {}))

        # For compatibility with old cfg object
        config["use_crewai_script_generation"] = config.get("crew", {}).get("enabled", True)
        config["use_three_stage_quality_check"] = not config.get("crew", {}).get("enabled", True)
        config["max_video_duration_minutes"] = config.get("video", {}).get("max_duration_minutes", 15)

        return cls(**config)


# グローバル設定インスタンス
settings = AppSettings.load()
