#!/usr/bin/env python3
"""
システム環境検証スクリプト
- API認証情報の確認
- VOICEVOX Nemo serverの起動と動作確認
- 必要なディレクトリの存在確認
- 依存関係のチェック
"""

import os
import subprocess
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging

from dotenv import load_dotenv

# ロギング設定
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# .envファイルを読み込み
load_dotenv(project_root / ".env")


class SystemVerifier:
    """システム検証クラス"""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        # VOICEVOX設定を settings から取得
        from app.config.settings import settings
        self.voicevox_port = settings.tts_voicevox_port
        self.voicevox_speaker = settings.tts_voicevox_speaker
        self.voicevox_manager = self.project_root / "scripts" / "voicevox_manager.sh"
        self.errors = []
        self.warnings = []

    def check_env_file(self) -> bool:
        """環境変数ファイルの存在確認"""
        logger.info("1. Checking .env file...")
        env_path = self.project_root / ".env"

        if not env_path.exists():
            self.errors.append(".env file not found")
            logger.error("❌ .env file not found")
            return False

        logger.info("✅ .env file exists")
        return True

    def check_api_keys(self) -> bool:
        """API認証情報の確認"""
        logger.info("2. Checking API keys...")

        required_keys = {
            "GEMINI_API_KEY": "Gemini API (Primary)",
            "PIXABAY_API_KEY": "Pixabay (Images)",
        }

        optional_keys = {
            "PERPLEXITY_API_KEY": "Perplexity (News)",
            "NEWSAPI_API_KEY": "NewsAPI (Fallback)",
            "ELEVENLABS_API_KEY": "ElevenLabs TTS",
            "OPENAI_API_KEY": "OpenAI TTS",
            "GOOGLE_APPLICATION_CREDENTIALS": "Google Sheets",
            "PEXELS_API_KEY": "Pexels (Stock Footage)",
        }

        all_ok = True

        # 必須キーのチェック
        for key, name in required_keys.items():
            value = os.getenv(key)
            if not value or value == "your_key_here":
                self.errors.append(f"{name} ({key}) not configured")
                logger.error(f"❌ {name}: NOT CONFIGURED")
                all_ok = False
            else:
                logger.info(f"✅ {name}: configured ({value[:10]}...)")

        # オプショナルキーのチェック
        for key, name in optional_keys.items():
            value = os.getenv(key)
            if not value or value == "your_key_here":
                self.warnings.append(f"{name} ({key}) not configured (optional)")
                logger.warning(f"⚠️  {name}: not configured (optional)")
            else:
                logger.info(f"✅ {name}: configured")

        return all_ok

    def check_voicevox_status(self) -> bool:
        """VOICEVOX serverの動作確認"""
        logger.info("3. Checking VOICEVOX Nemo server...")

        try:
            result = subprocess.run([str(self.voicevox_manager), "status"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                logger.info(f"✅ VOICEVOX Nemo is running on port {self.voicevox_port} (speaker: {self.voicevox_speaker})")
                return True
            else:
                logger.warning("⚠️  VOICEVOX Nemo is not running")
                return False
        except FileNotFoundError:
            logger.warning(f"⚠️  VOICEVOX manager script not found: {self.voicevox_manager}")
            return False
        except Exception as e:
            logger.warning(f"⚠️  Failed to check VOICEVOX: {e}")
            return False

    def start_voicevox_server(self) -> bool:
        """VOICEVOX Nemo serverを起動"""
        logger.info("4. Starting VOICEVOX Nemo server...")

        if not self.voicevox_manager.exists():
            logger.error(f"❌ VOICEVOX manager script not found: {self.voicevox_manager}")
            self.warnings.append("VOICEVOX manager script not found (will use fallback TTS)")
            return False

        try:
            result = subprocess.run([str(self.voicevox_manager), "start"], capture_output=True, text=True, timeout=120)

            if result.returncode == 0:
                logger.info("✅ VOICEVOX Nemo started successfully")
                return True
            else:
                logger.warning(f"⚠️  VOICEVOX Nemo startup failed: {result.stderr}")
                self.warnings.append("VOICEVOX Nemo could not be started (will use fallback TTS)")
                return False

        except subprocess.TimeoutExpired:
            logger.error("❌ VOICEVOX Nemo startup timeout")
            self.warnings.append("VOICEVOX startup timeout (will use fallback TTS)")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to start VOICEVOX: {e}")
            self.warnings.append(f"VOICEVOX startup error: {e}")
            return False

    def check_directories(self) -> bool:
        """必要なディレクトリの確認と作成"""
        logger.info("5. Checking required directories...")

        required_dirs = [
            "logs",
            "output",
            "temp",
            "cache",
        ]

        all_ok = True
        for dir_name in required_dirs:
            dir_path = self.project_root / dir_name
            if not dir_path.exists():
                logger.warning(f"⚠️  Creating missing directory: {dir_name}")
                dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ {dir_name}/ exists")

        return all_ok

    def check_virtual_environment(self) -> bool:
        """仮想環境の確認"""
        logger.info("6. Checking virtual environment...")

        if not hasattr(sys, "real_prefix") and not (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix):
            logger.warning("⚠️  Not running in a virtual environment")
            self.warnings.append("Not running in virtual environment (recommended)")
            return False

        logger.info(f"✅ Running in virtual environment: {sys.prefix}")
        return True

    def test_voicevox_synthesis(self) -> bool:
        """VOICEVOX音声合成のテスト"""
        logger.info("7. Testing VOICEVOX synthesis...")

        if not self.check_voicevox_status():
            logger.warning("⚠️  Skipping synthesis test (server not running)")
            return False

        if not self.voicevox_manager.exists():
            logger.warning("⚠️  VOICEVOX manager script not found")
            return False

        try:
            result = subprocess.run([str(self.voicevox_manager), "test"], capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                logger.info("✅ VOICEVOX synthesis test successful")
                return True
            else:
                logger.error(f"❌ Synthesis test failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("❌ Synthesis test timeout")
            return False
        except Exception as e:
            logger.error(f"❌ Synthesis test failed: {e}")
            return False

    def print_summary(self):
        """検証結果のサマリーを表示"""
        logger.info("\n" + "=" * 60)
        logger.info("VERIFICATION SUMMARY")
        logger.info("=" * 60)

        if self.errors:
            logger.error(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                logger.error(f"  - {error}")

        if self.warnings:
            logger.warning(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                logger.warning(f"  - {warning}")

        if not self.errors and not self.warnings:
            logger.info("\n✅ ALL CHECKS PASSED!")
        elif not self.errors:
            logger.info("\n✅ SYSTEM READY (with warnings)")
        else:
            logger.error("\n❌ SYSTEM NOT READY - Please fix errors above")

        logger.info("=" * 60)

    def run(self) -> bool:
        """全検証を実行"""
        logger.info("Starting system verification...\n")

        # 1. .envファイルチェック
        self.check_env_file()

        # 2. API認証情報チェック
        self.check_api_keys()

        # 3. VOICEVOXステータス確認
        voicevox_running = self.check_voicevox_status()

        # 4. VOICEVOX起動（必要な場合）
        if not voicevox_running:
            logger.info("4. Attempting to start VOICEVOX Nemo server...")
            voicevox_started = self.start_voicevox_server()
            if not voicevox_started:
                logger.warning("⚠️  VOICEVOX Nemo not available - will use fallback TTS (gTTS, pyttsx3)")
        else:
            logger.info("4. VOICEVOX Nemo already running, skipping startup")

        # 5. ディレクトリチェック
        self.check_directories()

        # 6. 仮想環境チェック
        self.check_virtual_environment()

        # 7. VOICEVOX合成テスト（起動している場合のみ）
        if self.check_voicevox_status():
            self.test_voicevox_synthesis()
        else:
            logger.warning("7. Skipping VOICEVOX synthesis test (server not running)")

        # サマリー表示
        self.print_summary()

        # エラーがなければ成功
        return len(self.errors) == 0


def main():
    """メイン処理"""
    verifier = SystemVerifier()
    success = verifier.run()

    if success:
        logger.info("\n🚀 System is ready to run!")
        logger.info("Run: python -m app.main daily")
        sys.exit(0)
    else:
        logger.error("\n⛔ System verification failed")
        logger.error("Please fix the errors above before running the system")
        sys.exit(1)


if __name__ == "__main__":
    main()
