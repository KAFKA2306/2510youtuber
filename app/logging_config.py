import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
import requests
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
LOG_FORMAT = "[%(asctime)s] %(levelname)-8s %(name)s | %(message)s"
DATE_FORMAT = "%H:%M:%S"
_STANDARD_LOG_RECORD_FIELDS: Iterable[str] = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
    "asctime",
    "session_id",
    "run_id",
}
def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
def _safe_json(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_safe_json(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _safe_json(v) for k, v in value.items()}
    return str(value)
class JsonLineFormatter(logging.Formatter):
    """Serialize log records as JSON for structured storage."""
    def format(self, record: logging.LogRecord) -> str:
        base: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "session_id": getattr(record, "session_id", None),
            "run_id": getattr(record, "run_id", None),
        }
        if record.exc_info:
            base["exception"] = self.formatException(record.exc_info)
        for attr in ("event", "step", "status", "duration", "agent", "task", "api", "metric"):
            value = getattr(record, attr, None)
            if value is not None:
                base[attr] = _safe_json(value)
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_LOG_RECORD_FIELDS and not key.startswith("_")
        }
        if extras:
            base["extra"] = {key: _safe_json(value) for key, value in extras.items()}
        return json.dumps(base, ensure_ascii=False)
class DiscordHandler(logging.Handler):
    """スマホ向けに短縮化したDiscord通知ハンドラ"""
    def emit(self, record: logging.LogRecord) -> None:
        try:
            if not DISCORD_WEBHOOK:
                return
            run_id = getattr(record, "run_id", "") or "-"
            session_id = getattr(record, "session_id", "") or "-"
            short_id = run_id[:4] if run_id and run_id != "-" else session_id[:4]
            msg = ""
            if record.levelno >= logging.ERROR:
                step = getattr(record, "step", "")
                error_msg = record.getMessage().split("\n")[0][:80]
                msg = f"❌ Error {short_id} {step}\n{error_msg}"
            elif record.levelno == logging.WARNING:
                summary = record.getMessage().split("\n")[0][:60]
                msg = f"⚠️ Warning {short_id} {summary}"
            elif record.levelno == logging.INFO and "Success" in record.getMessage():
                parts = record.getMessage().split()
                if len(parts) >= 4:
                    msg = f"✅ Success {parts[1][:4]} ({parts[-1]}) {parts[2]}"
            if msg:
                requests.post(DISCORD_WEBHOOK, json={"content": msg}, timeout=5)
        except Exception:
            self.handleError(record)
class RunContextFilter(logging.Filter):
    """Inject session/run identifiers into every log record."""
    def __init__(self, session_id: str) -> None:
        super().__init__()
        self.session_id = session_id
        self.run_id: Optional[str] = None
        self.context: Dict[str, Any] = {}
    def set_context(self, run_id: Optional[str] = None, **context: Any) -> None:
        self.run_id = run_id or self.run_id
        self.context.update({k: v for k, v in context.items() if v is not None})
    def filter(self, record: logging.LogRecord) -> bool:
        record.session_id = self.session_id
        if self.run_id is not None:
            record.run_id = self.run_id
        for key, value in self.context.items():
            if not hasattr(record, key):
                setattr(record, key, value)
        return True
@dataclass
class LoggingSession:
    """Holds metadata about the current logging session."""
    session_id: str
    base_dir: Path
    run_dir: Path
    text_log_path: Path
    error_log_path: Path
    structured_log_path: Path
    metadata_path: Path
    created_at: str = field(default_factory=_utcnow_iso)
    _filter: Optional[RunContextFilter] = field(default=None, repr=False)
    def initialize_metadata(self, log_level: int) -> None:
        payload = {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "log_level": logging.getLevelName(log_level),
            "paths": {
                "text": str(self.text_log_path),
                "errors": str(self.error_log_path),
                "structured": str(self.structured_log_path),
            },
        }
        self.metadata_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    def attach_filter(self, filter_: RunContextFilter) -> None:
        self._filter = filter_
    def bind_workflow_run(self, run_id: str, mode: Optional[str] = None) -> None:
        self._update_metadata({"workflow_run_id": run_id, "mode": mode})
        if self._filter:
            self._filter.set_context(run_id=run_id, mode=mode)
    def mark_status(self, status: str, **fields: Any) -> None:
        payload = {"status": status, "updated_at": _utcnow_iso()}
        payload.update({k: _safe_json(v) for k, v in fields.items()})
        self._update_metadata(payload)
    def _update_metadata(self, updates: Dict[str, Any]) -> None:
        if self.metadata_path.exists():
            current = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        else:
            current = {}
        current.update({k: v for k, v in updates.items() if v is not None})
        self.metadata_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
_CURRENT_SESSION: Optional[LoggingSession] = None
def get_log_session() -> Optional[LoggingSession]:
    """Return the active logging session, if any."""
    return _CURRENT_SESSION
class WorkflowLogger:
    """ワークフロー専用のログヘルパー"""
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    def step_start(self, step_name: str, details: str = "") -> None:
        """ステップ開始ログ"""
        message = f"Starting workflow step: {step_name}"
        if details:
            message += f" ({details})"
        self.logger.info(message, extra={"event": "step_start", "step": step_name, "details": details})
    def step_end(self, step_name: str, duration: Optional[float] = None, status: str = "SUCCESS") -> None:
        """ステップ終了ログ"""
        emoji = "✅" if status.upper() == "SUCCESS" else "❌"
        suffix = f" ({duration:.2f}s)" if duration is not None else ""
        self.logger.info(
            f"{emoji} Step {step_name} completed{suffix}",
            extra={"event": "step_end", "step": step_name, "status": status, "duration": duration},
        )
    def agent_start(self, agent_name: str, task_name: str) -> None:
        """エージェント実行開始"""
        self.logger.info(
            f"🤖 Agent [{agent_name}] starting task: {task_name}",
            extra={"event": "agent_start", "agent": agent_name, "task": task_name},
        )
    def agent_end(self, agent_name: str, output_length: int = 0, status: str = "SUCCESS") -> None:
        """エージェント実行終了"""
        emoji = "✅" if status.upper() == "SUCCESS" else "❌"
        self.logger.info(
            f"{emoji} Agent [{agent_name}] completed (output: {output_length} chars)",
            extra={
                "event": "agent_end",
                "agent": agent_name,
                "status": status,
                "output_length": output_length,
            },
        )
    def api_call(self, api_name: str, method: str = "", status: str = "") -> None:
        """API呼び出しログ"""
        message = f"🌐 API [{api_name}] {method}".strip()
        if status:
            message += f" -> {status}"
        self.logger.debug(
            message,
            extra={"event": "api_call", "api": api_name, "method": method, "status": status},
        )
    def validation(self, item_name: str, result: bool, details: str = "") -> None:
        """検証結果ログ"""
        emoji = "✅" if result else "❌"
        message = f"{emoji} Validation [{item_name}]: {result}"
        if details:
            message += f" - {details}"
        self.logger.info(
            message,
            extra={"event": "validation", "item": item_name, "result": result, "details": details},
        )
    def metric(self, metric_name: str, value: Any) -> None:
        """メトリクスログ"""
        self.logger.info(
            f"📊 Metric [{metric_name}]: {value}",
            extra={"event": "metric", "metric": metric_name, "value": value},
        )
    def progress(self, current: int, total: int, item: str = "") -> None:
        """進捗ログ"""
        percentage = (current / total * 100) if total > 0 else 0
        bar = "█" * int(percentage / 5) + "░" * (20 - int(percentage / 5))
        self.logger.info(
            f"⏳ Progress [{bar}] {percentage:.1f}% ({current}/{total}) {item}",
            extra={
                "event": "progress",
                "current": current,
                "total": total,
                "item": item,
                "percentage": percentage,
            },
        )
def setup_logging(log_level: int = logging.INFO, log_dir: str = "logs", session_id: Optional[str] = None) -> LoggingSession:
    """詳細ログシステムのセットアップ"""
    base_dir = Path(log_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = base_dir / "runs"
    runs_dir.mkdir(exist_ok=True)
    generated_id = session_id or f"session_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    run_dir = runs_dir / generated_id
    run_dir.mkdir(exist_ok=True)
    session = LoggingSession(
        session_id=generated_id,
        base_dir=base_dir,
        run_dir=run_dir,
        text_log_path=run_dir / "workflow.log",
        error_log_path=run_dir / "errors.log",
        structured_log_path=run_dir / "events.jsonl",
        metadata_path=run_dir / "metadata.json",
    )
    session.text_log_path.touch(exist_ok=True)
    session.error_log_path.touch(exist_ok=True)
    session.structured_log_path.touch(exist_ok=True)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.filters.clear()
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    file_handler = logging.FileHandler(session.text_log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    error_handler = logging.FileHandler(session.error_log_path, encoding="utf-8")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    structured_handler = logging.FileHandler(session.structured_log_path, encoding="utf-8")
    structured_handler.setLevel(logging.DEBUG)
    structured_handler.setFormatter(JsonLineFormatter())
    discord_handler = DiscordHandler()
    discord_handler.setLevel(logging.WARNING)
    for handler in (console_handler, file_handler, error_handler, structured_handler, discord_handler):
        root_logger.addHandler(handler)
    context_filter = RunContextFilter(session.session_id)
    root_logger.addFilter(context_filter)
    session.attach_filter(context_filter)
    session.initialize_metadata(log_level)
    global _CURRENT_SESSION
    _CURRENT_SESSION = session
    return session
