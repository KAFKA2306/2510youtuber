"""Discord通知モジュール.
Provides asynchronous notification helpers so workflow execution does not block
when sending webhook messages.
"""
from __future__ import annotations
import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional
import httpx
from app.config_prompts.settings import settings as cfg
from app.notifications.interfaces import Notifier
logger = logging.getLogger(__name__)
class DiscordNotifier(Notifier):
    """Discord webhook notifier supporting async + sync execution paths."""
    def __init__(
        self,
        webhook_url: Optional[str] = None,
        *,
        timeout: float = 10.0,
        client_factory: Optional[Callable[[], httpx.AsyncClient]] = None,
        run_sync: Optional[Callable[[Awaitable[bool]], bool]] = None,
    ) -> None:
        self.webhook_url = webhook_url if webhook_url is not None else cfg.discord_webhook_url
        self.enabled = bool(self.webhook_url)
        self._timeout = timeout
        self._client_factory = client_factory or self._default_client_factory
        self._run_sync = run_sync or asyncio.run
        if not self.enabled:
            logger.warning("Discord webhook URL not configured, notifications disabled")
    def _default_client_factory(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._timeout)
    def _run_blocking(self, coroutine: Awaitable[bool]) -> bool:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return self._run_sync(coroutine)
        raise RuntimeError("notify_blocking cannot be used inside an active event loop")
    async def notify(
        self,
        message: str,
        *,
        level: str = "info",
        title: Optional[str] = None,
        fields: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send a Discord notification asynchronously."""
        if not self.enabled:
            logger.info("[Discord disabled] %s", message)
            return False
        level_config = {
            "info": {"color": "
            "success": {"color": "
            "warning": {"color": "
            "error": {"color": "
            "debug": {"color": "
        }
        config = level_config.get(level, level_config["info"])
        icon = config["icon"]
        color = config["color"]
        embed_title = title or "YouTube Automation"
        payload = {
            "embeds": [
                {
                    "color": int(color.replace("
                    "title": f"{icon} {embed_title}",
                    "description": message,
                    "footer": {"text": "YouTube Automation System"},
                    "timestamp": datetime.fromtimestamp(time.time()).isoformat(),
                }
            ]
        }
        if fields:
            payload["embeds"][0]["fields"] = [
                {"name": key, "value": str(value), "inline": True}
                for key, value in fields.items()
            ]
        try:
            async with self._client_factory() as client:
                response = await client.post(self.webhook_url, json=payload)
                response.raise_for_status()
            logger.debug("Discord notification sent: %s - %s", level, message[:50])
            return True
        except httpx.HTTPStatusError as exc:
            request_url = exc.request.url if exc.request else "N/A"
            response_text = exc.response.text if exc.response else "<no response>"
            logger.error(
                "Failed to send Discord notification due to a client or server error: %s\n"
                "URL: %s\n"
                "Response: %s",
                exc,
                request_url,
                response_text,
            )
            return False
        except Exception as exc:
            logger.error("Failed to send Discord notification: %s", exc)
            return False
    def notify_blocking(
        self,
        message: str,
        *,
        level: str = "info",
        title: Optional[str] = None,
        fields: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Synchronously send a notification (runs its own event loop)."""
        return self._run_blocking(self.notify(message, level=level, title=title, fields=fields))
    async def notify_run_start(self, run_id: str, mode: str) -> bool:
        message = "動画生成を開始しました"
        fields = {"実行ID": run_id, "モード": mode, "開始時刻": time.strftime("%Y-%m-%d %H:%M:%S")}
        return await self.notify(message=message, level="info", title="🚀 実行開始", fields=fields)
    def notify_run_start_blocking(self, run_id: str, mode: str) -> bool:
        return self._run_blocking(self.notify_run_start(run_id, mode))
    async def notify_run_success(
        self,
        run_id: str,
        duration_sec: int,
        video_url: Optional[str] = None,
        title: Optional[str] = None,
    ) -> bool:
        duration_min = duration_sec // 60
        duration_sec_remain = duration_sec % 60
        message = "動画生成が完了しました！"
        fields: Dict[str, Any] = {
            "実行ID": run_id,
            "処理時間": f"{duration_min}分{duration_sec_remain}秒",
            "完了時刻": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        if title:
            fields["動画タイトル"] = title[:100] + "..." if len(title) > 100 else title
        if video_url:
            fields["動画URL"] = video_url
        return await self.notify(message=message, level="success", title="✅ 実行完了", fields=fields)
    def notify_run_success_blocking(
        self,
        run_id: str,
        duration_sec: int,
        video_url: Optional[str] = None,
        title: Optional[str] = None,
    ) -> bool:
        return self._run_blocking(
            self.notify_run_success(run_id, duration_sec, video_url=video_url, title=title)
        )
    async def notify_run_error(
        self, run_id: str, error_message: str, step: Optional[str] = None
    ) -> bool:
        message = "動画生成でエラーが発生しました"
        fields: Dict[str, Any] = {
            "実行ID": run_id,
            "エラー時刻": time.strftime("%Y-%m-%d %H:%M:%S"),
            "エラー": error_message[:200] + "..." if len(error_message) > 200 else error_message,
        }
        if step:
            fields["エラー箇所"] = step
        return await self.notify(message=message, level="error", title="❌ 実行失敗", fields=fields)
    def notify_run_error_blocking(
        self, run_id: str, error_message: str, step: Optional[str] = None
    ) -> bool:
        return self._run_blocking(self.notify_run_error(run_id, error_message, step))
    async def notify_step_progress(
        self, run_id: str, step_name: str, progress: Optional[str] = None
    ) -> bool:
        message = f"ステップ実行中: {step_name}"
        fields: Dict[str, Any] = {"実行ID": run_id, "現在時刻": time.strftime("%H:%M:%S")}
        if progress:
            fields["詳細"] = progress
        return await self.notify(message=message, level="info", title="⏳ 進捗", fields=fields)
    def notify_step_progress_blocking(
        self, run_id: str, step_name: str, progress: Optional[str] = None
    ) -> bool:
        return self._run_blocking(self.notify_step_progress(run_id, step_name, progress))
    async def notify_status(
        self,
        run_id: str,
        status: str,
        duration: Optional[int] = None,
        error: Optional[str] = None,
    ) -> bool:
        if status == "started":
            message = f"🚀 実行開始 (ID: {run_id})"
            level = "info"
            fields = {"実行ID": run_id, "開始時刻": time.strftime("%Y-%m-%d %H:%M:%S")}
        elif status == "completed":
            duration_str = f"{duration}秒" if duration else "不明"
            message = f"✅ 実行完了 (ID: {run_id}, 処理時間: {duration_str})"
            level = "success"
            fields = {
                "実行ID": run_id,
                "処理時間": duration_str,
                "完了時刻": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        elif status == "error":
            message = f"❌ 実行失敗 (ID: {run_id})"
            level = "error"
            fields = {
                "実行ID": run_id,
                "エラー時刻": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            if error:
                fields["エラー"] = error[:200] + "..." if len(error) > 200 else error
        else:
            message = f"状態更新: {status} (ID: {run_id})"
            level = "info"
            fields = {"実行ID": run_id, "ステータス": status}
        return await self.notify(message=message, level=level, fields=fields)
    def notify_status_blocking(
        self, run_id: str, status: str, duration: Optional[int] = None, error: Optional[str] = None
    ) -> bool:
        return self._run_blocking(
            self.notify_status(run_id, status=status, duration=duration, error=error)
        )
    async def notify_api_quota_warning(self, api_name: str, usage_info: str) -> bool:
        message = f"{api_name} APIの使用量が上限に近づいています"
        fields = {
            "API": api_name,
            "使用量情報": usage_info,
            "確認時刻": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        return await self.notify(
            message=message, level="warning", title="⚠️ API制限警告", fields=fields
        )
    def notify_api_quota_warning_blocking(self, api_name: str, usage_info: str) -> bool:
        return self._run_blocking(self.notify_api_quota_warning(api_name, usage_info))
    async def notify_system_health(self, health_data: Dict[str, Any]) -> bool:
        all_ok = all(
            status.get("configured", False) or status.get("status") == "OK"
            for status in health_data.values()
            if isinstance(status, dict)
        )
        level = "success" if all_ok else "warning"
        message = "システムヘルスチェック結果"
        fields: Dict[str, Any] = {}
        for service, status in health_data.items():
            if isinstance(status, dict):
                if "configured" in status:
                    fields[service] = "✓ 設定済み" if status["configured"] else "✗ 未設定"
                elif "status" in status:
                    fields[service] = f"{status['status']}"
                else:
                    fields[service] = str(status)
            else:
                fields[service] = str(status)
        return await self.notify(message=message, level=level, title="🏥 ヘルスチェック", fields=fields)
    def notify_system_health_blocking(self, health_data: Dict[str, Any]) -> bool:
        return self._run_blocking(self.notify_system_health(health_data))
    async def notify_daily_summary(self, summary_data: Dict[str, Any]) -> bool:
        total_runs = summary_data.get("total_runs", 0)
        successful_runs = summary_data.get("successful_runs", 0)
        failed_runs = summary_data.get("failed_runs", 0)
        avg_duration = summary_data.get("avg_duration_sec", 0)
        success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0
        message = "本日の実行サマリー"
        fields: Dict[str, Any] = {
            "総実行数": f"{total_runs}回",
            "成功": f"{successful_runs}回",
            "失敗": f"{failed_runs}回",
            "成功率": f"{success_rate:.1f}%",
            "平均処理時間": f"{avg_duration // 60}分{avg_duration % 60}秒",
        }
        if "generated_videos" in summary_data:
            fields["生成動画数"] = f"{len(summary_data['generated_videos'])}本"
        level = "success" if failed_runs == 0 else ("warning" if success_rate >= 80 else "error")
        return await self.notify(message=message, level=level, title="📊 日次サマリー", fields=fields)
    def notify_daily_summary_blocking(self, summary_data: Dict[str, Any]) -> bool:
        return self._run_blocking(self.notify_daily_summary(summary_data))
    async def test_notification(self) -> bool:
        return await self.notify(
            message="Discord通知のテストメッセージです",
            level="info",
            title="🧪 テスト通知",
            fields={
                "テスト時刻": time.strftime("%Y-%m-%d %H:%M:%S"),
                "システム": "YouTube Automation",
            },
        )
    def test_notification_blocking(self) -> bool:
        return self._run_blocking(self.test_notification())
discord_notifier = DiscordNotifier()
def notify(message: str, level: str = "info") -> bool:
    """基本通知の簡易関数 (同期)."""
    return discord_notifier.notify_blocking(message, level=level)
def notify_run_start(run_id: str, mode: str) -> bool:
    """実行開始通知の簡易関数 (同期)."""
    return discord_notifier.notify_run_start_blocking(run_id, mode)
def notify_run_success(
    run_id: str, duration_sec: int, video_url: Optional[str] = None, title: Optional[str] = None
) -> bool:
    """実行成功通知の簡易関数 (同期)."""
    return discord_notifier.notify_run_success_blocking(run_id, duration_sec, video_url, title)
def notify_run_error(run_id: str, error_message: str, step: Optional[str] = None) -> bool:
    """実行エラー通知の簡易関数 (同期)."""
    return discord_notifier.notify_run_error_blocking(run_id, error_message, step)
def notify_step_progress(run_id: str, step_name: str, progress: Optional[str] = None) -> bool:
    """ステップ進捗通知の簡易関数 (同期)."""
    return discord_notifier.notify_step_progress_blocking(run_id, step_name, progress)
if __name__ == "__main__":
    print("Testing Discord notifications...")
    print(f"Discord enabled: {discord_notifier.enabled}")
    if discord_notifier.enabled:
        print(f"Webhook URL configured: {bool(discord_notifier.webhook_url)}")
        result = discord_notifier.test_notification_blocking()
        print(f"Test notification result: {result}")
    else:
        print("Discord not configured, skipping test")
