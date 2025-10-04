import logging
import sys
from pathlib import Path
from datetime import datetime

class ColoredFormatter(logging.Formatter):
    """色付きログフォーマッター"""
    
    COLORS = {
        'DEBUG': '\033[36m',      # シアン
        'INFO': '\033[32m',       # 緑
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 赤
        'CRITICAL': '\033[35m',   # マゼンタ
        'RESET': '\033[0m'
    }
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # タイムスタンプを短縮
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        
        # モジュール名を短縮
        module = record.name.split('.')[-1][:15]
        
        # レベルを固定幅に
        level = f"{record.levelname:8}"
        
        # メッセージ
        message = record.getMessage()
        
        return f"{color}[{timestamp}] {level} {module:15} | {message}{reset}"

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
    
    # コンソールハンドラー（色付き）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(ColoredFormatter())
    root_logger.addHandler(console_handler)
    
    # ファイルハンドラー（詳細）
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_handler = logging.FileHandler(
        log_path / f"workflow_{timestamp}.log",
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    )
    root_logger.addHandler(file_handler)
    
    # エラー専用ログ
    error_handler = logging.FileHandler(
        log_path / "errors.log",
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(
        logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)-20s | %(pathname)s:%(lineno)d\n%(message)s\n',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    )
    root_logger.addHandler(error_handler)
    
    return root_logger

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
