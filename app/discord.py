"""Discord通知モジュール

システムの実行状況や結果をDiscordに通知します。
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional

import httpx

from app.config_prompts.settings import settings as cfg

logger = logging.getLogger(__name__)


class DiscordNotifier:
    """Discord通知クラス"""

    def __init__(self):
        self.webhook_url = cfg.discord_webhook_url
        self.enabled = bool(self.webhook_url)

        if not self.enabled:
            logger.warning("Discord webhook URL not configured, notifications disabled")

    def notify(
        self, message: str, level: str = "info", title: Optional[str] = None, fields: Optional[Dict[str, Any]] = None
    ) -> bool:
        """基本的なDiscord通知

        Args:
            message: 通知メッセージ
            level: ログレベル (info/warning/error/success)
            title: タイトル（省略時は自動設定）
            fields: 追加フィールド

        Returns:
            送信成功時True

        """
        if not self.enabled:
            logger.info(f"[Discord disabled] {message}")
            return False

        try:
            # レベルに応じた色とアイコン
            level_config = {
                "info": {"color": "#36a64f", "icon": "ℹ️"},
                "success": {"color": "#36a64f", "icon": "✅"},
                "warning": {"color": "#ff9500", "icon": "⚠️"},
                "error": {"color": "#ff0000", "icon": "❌"},
                "debug": {"color": "#808080", "icon": "🔧"},
            }

            config = level_config.get(level, level_config["info"])
            icon = config["icon"]
            color = config["color"]

            # デフォルトタイトル
            if not title:
                title = "YouTube Automation"

            # 基本ペイロード
            payload = {
                "embeds": [
                    {
                        "color": int(color.replace("#", ""), 16),
                        "title": f"{icon} {title}",
                        "description": message,
                        "footer": {"text": "YouTube Automation System"},
                        "timestamp": datetime.fromtimestamp(time.time()).isoformat(),
                    }
                ]
            }

            # 追加フィールドがある場合
            if fields:
                discord_fields = []
                for key, value in fields.items():
                    discord_fields.append({"name": key, "value": str(value), "inline": True})
                payload["embeds"][0]["fields"] = discord_fields

            # Discord送信
            response = httpx.post(self.webhook_url, json=payload, timeout=10.0)
            response.raise_for_status()

            logger.debug(f"Discord notification sent: {level} - {message[:50]}...")
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Failed to send Discord notification due to a client or server error: {e}\n"
                f"URL: {e.request.url}\n"
                f"Response: {e.response.text}"
            )
            return False
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
            return False

    def notify_run_start(self, run_id: str, mode: str) -> bool:
        """実行開始通知

        Args:
            run_id: 実行ID
            mode: 実行モード

        Returns:
            送信成功時True

        """
        message = "動画生成を開始しました"
        fields = {"実行ID": run_id, "モード": mode, "開始時刻": time.strftime("%Y-%m-%d %H:%M:%S")}

        return self.notify(message=message, level="info", title="🚀 実行開始", fields=fields)

    def notify_run_success(
        self, run_id: str, duration_sec: int, video_url: Optional[str] = None, title: Optional[str] = None
    ) -> bool:
        """実行成功通知

        Args:
            run_id: 実行ID
            duration_sec: 処理時間（秒）
            video_url: 動画URL
            title: 動画タイトル

        Returns:
            送信成功時True

        """
        duration_min = duration_sec // 60
        duration_sec_remain = duration_sec % 60

        message = "動画生成が完了しました！"
        fields = {
            "実行ID": run_id,
            "処理時間": f"{duration_min}分{duration_sec_remain}秒",
            "完了時刻": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        if title:
            fields["動画タイトル"] = title[:100] + "..." if len(title) > 100 else title

        if video_url:
            fields["動画URL"] = video_url

        return self.notify(message=message, level="success", title="✅ 実行完了", fields=fields)

    def notify_run_error(self, run_id: str, error_message: str, step: Optional[str] = None) -> bool:
        """実行エラー通知

        Args:
            run_id: 実行ID
            error_message: エラーメッセージ
            step: エラーが発生したステップ

        Returns:
            送信成功時True

        """
        message = "動画生成でエラーが発生しました"
        fields = {
            "実行ID": run_id,
            "エラー時刻": time.strftime("%Y-%m-%d %H:%M:%S"),
            "エラー": error_message[:200] + "..." if len(error_message) > 200 else error_message,
        }

        if step:
            fields["エラー箇所"] = step

        return self.notify(message=message, level="error", title="❌ 実行失敗", fields=fields)

    def notify_step_progress(self, run_id: str, step_name: str, progress: Optional[str] = None) -> bool:
        """ステップ進捗通知

        Args:
            run_id: 実行ID
            step_name: ステップ名
            progress: 進捗詳細

        Returns:
            送信成功時True

        """
        message = f"ステップ実行中: {step_name}"
        fields = {"実行ID": run_id, "現在時刻": time.strftime("%H:%M:%S")}

        if progress:
            fields["詳細"] = progress

        return self.notify(message=message, level="info", title="⏳ 進捗", fields=fields)

    def notify_status(
        self, run_id: str, status: str, duration: Optional[int] = None, error: Optional[str] = None
    ) -> bool:
        """詳細ステータス通知

        Args:
            run_id: 実行ID
            status: ステータス (started/completed/error)
            duration: 処理時間（秒）
            error: エラーメッセージ

        Returns:
            送信成功時True

        """
        if status == "started":
            message = f"🚀 実行開始 (ID: {run_id})"
            level = "info"
            fields = {"実行ID": run_id, "開始時刻": time.strftime("%Y-%m-%d %H:%M:%S")}
        elif status == "completed":
            duration_str = f"{duration}秒" if duration else "不明"
            message = f"✅ 実行完了 (ID: {run_id}, 処理時間: {duration_str})"
            level = "success"
            fields = {"実行ID": run_id, "処理時間": duration_str, "完了時刻": time.strftime("%Y-%m-%d %H:%M:%S")}
        elif status == "error":
            message = f"❌ 実行失敗 (ID: {run_id})"
            level = "error"
            fields = {"実行ID": run_id, "エラー時刻": time.strftime("%Y-%m-%d %H:%M:%S")}
            if error:
                fields["エラー"] = error[:200] + "..." if len(error) > 200 else error
        else:
            message = f"状態更新: {status} (ID: {run_id})"
            level = "info"
            fields = {"実行ID": run_id, "ステータス": status}

        return self.notify(message=message, level=level, fields=fields)

    def notify_api_quota_warning(self, api_name: str, usage_info: str) -> bool:
        """API使用量警告通知

        Args:
            api_name: API名
            usage_info: 使用量情報

        Returns:
            送信成功時True

        """
        message = f"{api_name} APIの使用量が上限に近づいています"
        fields = {"API": api_name, "使用量情報": usage_info, "確認時刻": time.strftime("%Y-%m-%d %H:%M:%S")}

        return self.notify(message=message, level="warning", title="⚠️ API制限警告", fields=fields)

    def notify_system_health(self, health_data: Dict[str, Any]) -> bool:
        """システムヘルスチェック通知

        Args:
            health_data: ヘルスチェック結果

        Returns:
            送信成功時True

        """
        # 全体のヘルス状況を判定
        all_ok = all(status.get("configured", False) or status.get("status") == "OK" for status in health_data.values())

        level = "success" if all_ok else "warning"
        message = "システムヘルスチェック結果"

        # フィールドに結果を整理
        fields = {}
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

        return self.notify(message=message, level=level, title="🏥 ヘルスチェック", fields=fields)

    def notify_daily_summary(self, summary_data: Dict[str, Any]) -> bool:
        """日次サマリー通知

        Args:
            summary_data: サマリーデータ

        Returns:
            送信成功時True

        """
        total_runs = summary_data.get("total_runs", 0)
        successful_runs = summary_data.get("successful_runs", 0)
        failed_runs = summary_data.get("failed_runs", 0)
        avg_duration = summary_data.get("avg_duration_sec", 0)

        success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0

        message = "本日の実行サマリー"
        fields = {
            "総実行数": f"{total_runs}回",
            "成功": f"{successful_runs}回",
            "失敗": f"{failed_runs}回",
            "成功率": f"{success_rate:.1f}%",
            "平均処理時間": f"{avg_duration // 60}分{avg_duration % 60}秒",
        }

        # 生成された動画がある場合
        if "generated_videos" in summary_data:
            fields["生成動画数"] = f"{len(summary_data['generated_videos'])}本"

        level = "success" if failed_runs == 0 else ("warning" if success_rate >= 80 else "error")

        return self.notify(message=message, level=level, title="📊 日次サマリー", fields=fields)

    def test_notification(self) -> bool:
        """テスト通知

        Returns:
            送信成功時True

        """
        return self.notify(
            message="Discord通知のテストメッセージです",
            level="info",
            title="🧪 テスト通知",
            fields={"テスト時刻": time.strftime("%Y-%m-%d %H:%M:%S"), "システム": "YouTube Automation"},
        )


# グローバルインスタンス
discord_notifier = DiscordNotifier()


# 簡易アクセス関数
def notify(message: str, level: str = "info") -> bool:
    """基本通知の簡易関数"""
    return discord_notifier.notify(message, level)


def notify_run_start(run_id: str, mode: str) -> bool:
    """実行開始通知の簡易関数"""
    return discord_notifier.notify_run_start(run_id, mode)


def notify_run_success(
    run_id: str, duration_sec: int, video_url: Optional[str] = None, title: Optional[str] = None
) -> bool:
    """実行成功通知の簡易関数"""
    return discord_notifier.notify_run_success(run_id, duration_sec, video_url, title)


def notify_run_error(run_id: str, error_message: str, step: Optional[str] = None) -> bool:
    """実行エラー通知の簡易関数"""
    return discord_notifier.notify_run_error(run_id, error_message, step)


def notify_step_progress(run_id: str, step_name: str, progress: Optional[str] = None) -> bool:
    """ステップ進捗通知の簡易関数"""
    return discord_notifier.notify_step_progress(run_id, step_name, progress)


if __name__ == "__main__":
    # テスト実行
    print("Testing Discord notifications...")

    # 設定チェック
    print(f"Discord enabled: {discord_notifier.enabled}")
    if discord_notifier.enabled:
        print(f"Webhook URL configured: {bool(discord_notifier.webhook_url)}")

        # テスト通知送信
        result = discord_notifier.test_notification()
        print(f"Test notification result: {result}")
    else:
        print("Discord not configured, skipping test")
