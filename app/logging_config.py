import logging
import os
import requests
from datetime import datetime
from pathlib import Path

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")

# Define common log format and date format
LOG_FORMAT = "[%(asctime)s] %(levelname)-8s %(name)s | %(message)s"
DATE_FORMAT = "%H:%M:%S"

class DiscordHandler(logging.Handler):
    """スマホ向けに短縮化したDiscord通知ハンドラ"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if not DISCORD_WEBHOOK:
                return

            run_id = getattr(record, "run_id", "") or "-"
            short_id = run_id[:4] if run_id else "----"
            msg = ""

            if record.levelno >= logging.ERROR:
                step = getattr(record, "step", "")
                error_msg = record.getMessage().split("\n")[0][:80]
                msg = f"❌ Error {short_id} {step}\n{error_msg}"

            elif record.levelno == logging.WARNING:
                summary = record.getMessage().split("\n")[0][:60]
                msg = f"⚠️ Warning {short_id} {summary}"

            elif record.levelno == logging.INFO and "Success" in record.getMessage():
                # 例: logger.info("Success run_id url 7m32s")
                parts = record.getMessage().split()
                if len(parts) >= 4:
                    msg = f"✅ Success {parts[1][:4]} ({parts[-1]}) {parts[2]}"

            if msg:
                requests.post(DISCORD_WEBHOOK, json={"content": msg}, timeout=5)

        except Exception:
            self.handleError(record)


class WorkflowLogger:
    """ワークフロー専用のログヘルパー"""
    
    def __init__(self, name):
        self.logger = logging.getLogger(name)
    
    def step_start(self, step_name, details=""):
        """ステップ開始ログ"""
        self.logger.info(f"{ '='*60}")
        self.logger.info(f"▶ STEP: {step_name}")
        if details:
            self.logger.info(f"  Details: {details}")
        self.logger.info(f"{ '='*60}")
    
    def step_end(self, step_name, duration=None, status="SUCCESS"):
        """ステップ終了ログ"""
        emoji = "✅" if status == "SUCCESS" else "❌"
        msg = f"{emoji} {step_name} completed"
        if duration:
            msg += f" ({duration:.2f}s)"
        self.logger.info(msg)
        self.logger.info(f"{ '='*60}\n")
    
    def agent_start(self, agent_name, task_name):
        """エージェント実行開始"""
        self.logger.info(f"🤖 Agent [{agent_name}] starting task: {task_name}")
    
    def agent_end(self, agent_name, output_length=0, status="SUCCESS"):
        """エージェント実行終了"""
        emoji = "✅" if status == "SUCCESS" else "❌"
        self.logger.info(f"{emoji} Agent [{agent_name}] completed (output: {output_length} chars)")
    
    def api_call(self, api_name, method="", status=""):
        """API呼び出しログ"""
        if status:
            self.logger.debug(f"🌐 API [{api_name}] {method} -> {status}")
        else:
            self.logger.debug(f"🌐 API [{api_name}] {method}")
    
    def validation(self, item_name, result, details=""):
        """検証結果ログ"""
        emoji = "✅" if result else "❌"
        msg = f"{emoji} Validation [{item_name}]: {result}"
        if details:
            msg += f" - {details}"
        self.logger.info(msg)
    
    def metric(self, metric_name, value):
        """メトリクスログ"""
        self.logger.info(f"📊 Metric [{metric_name}]: {value}")
    
    def progress(self, current, total, item=""):
        """進捗ログ"""
        percentage = (current / total * 100) if total > 0 else 0
        bar = "█" * int(percentage / 5) + "░" * (20 - int(percentage / 5))
        self.logger.info(f"⏳ Progress [{bar}] {percentage:.1f}% ({current}/{total}) {item}")

def setup_logging(log_level=logging.INFO, log_dir="logs"):
    """
    詳細ログシステムのセットアップ
    
    Args:
        log_level: ログレベル (DEBUG, INFO, WARNING, ERROR)
        log_dir: ログファイル保存ディレクトリ
    """
    # ログディレクトリ作成
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # ルートロガー取得
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # 既存のハンドラーをクリア
    root_logger.handlers.clear()
    
    # コンソールハンドラー
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    root_logger.addHandler(console_handler)
    
    # ファイルハンドラー（詳細）
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_handler = logging.FileHandler(
        log_path / f"workflow_{timestamp}.log",
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    root_logger.addHandler(file_handler)
    
    # エラー専用ログ
    error_handler = logging.FileHandler(
        log_path / "errors.log",
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    root_logger.addHandler(error_handler)

    # Discordハンドラーを追加
    discord_handler = DiscordHandler()
    discord_handler.setLevel(logging.WARNING) # WARNING以上のログをDiscordに送る
    root_logger.addHandler(discord_handler)
    
    return root_logger
