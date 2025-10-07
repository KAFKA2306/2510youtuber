"""動画フィードバック収集・分析ユーティリティ

YouTube Analytics APIやDiscord経由で視聴者のフィードバックを収集し、
背景テーマの継続的改善に活用します。
"""

import logging
import os
from datetime import datetime
from typing import Dict, Optional

import yaml

from .background_theme import get_theme_manager
from .models.video_review import VideoReviewResult

logger = logging.getLogger(__name__)


class VideoFeedbackCollector:
    """動画フィードバック収集クラス"""

    def __init__(self, feedback_file: str = "data/video_feedback.yaml"):
        self.feedback_file = feedback_file
        self.theme_manager = get_theme_manager()
        self._ensure_feedback_file()

    def _ensure_feedback_file(self):
        """フィードバックファイルが存在することを確認"""
        os.makedirs(os.path.dirname(self.feedback_file) if os.path.dirname(self.feedback_file) else ".", exist_ok=True)
        if not os.path.exists(self.feedback_file):
            with open(self.feedback_file, "w", encoding="utf-8") as f:
                yaml.safe_dump({}, f)

    def record_video_metadata(self, video_id: str, theme_name: str, metadata: Dict):
        """動画メタデータを記録（どのテーマを使ったか）"""
        try:
            with open(self.feedback_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            data[video_id] = {
                "theme_name": theme_name,
                "created_at": datetime.now().isoformat(),
                "metadata": metadata,
                "analytics": {},
            }

            with open(self.feedback_file, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

            logger.info(f"Recorded metadata for video {video_id} with theme {theme_name}")
        except Exception as e:
            logger.error(f"Failed to record video metadata: {e}")

    def update_analytics(self, video_id: str, analytics: Dict):
        """YouTube Analytics データを更新

        Args:
            video_id: 動画ID
            analytics: {
                'views': int,
                'likes': int,
                'dislikes': int,
                'comments': int,
                'avg_view_duration': float (seconds),
                'avg_view_percentage': float (0-100),
                'retention_rate': float (0-100),
                'click_through_rate': float (0-100),
            }
        """
        try:
            with open(self.feedback_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            if video_id not in data:
                logger.warning(f"Video {video_id} not found in feedback data")
                return

            data[video_id]["analytics"] = analytics
            data[video_id]["updated_at"] = datetime.now().isoformat()

            with open(self.feedback_file, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

            # テーマのパフォーマンス指標を更新
            theme_name = data[video_id]["theme_name"]
            retention_rate = analytics.get("retention_rate", 0.0)
            avg_view_duration = analytics.get("avg_view_duration", 0.0)

            self.theme_manager.update_performance_metrics(theme_name, avg_view_duration, retention_rate)

            # ポジティブフィードバックの判定（いいね/視聴の比率）
            views = analytics.get("views", 0)
            likes = analytics.get("likes", 0)
            if views > 0:
                like_ratio = likes / views
                if like_ratio > 0.05:  # 5%以上のいいね率はポジティブ
                    self.theme_manager.record_feedback(theme_name, positive=True)
                elif like_ratio < 0.02:  # 2%未満はネガティブ
                    self.theme_manager.record_feedback(theme_name, positive=False)

            logger.info(f"Updated analytics for video {video_id} (theme: {theme_name})")

        except Exception as e:
            logger.error(f"Failed to update analytics: {e}")

    def record_manual_feedback(self, video_id: str, positive: bool, comment: str = None):
        """手動フィードバックを記録（Discordやフォームから）

        Args:
            video_id: 動画ID
            positive: ポジティブかネガティブか
            comment: コメント（オプション）
        """
        try:
            with open(self.feedback_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            if video_id not in data:
                logger.warning(f"Video {video_id} not found, creating new entry")
                data[video_id] = {
                    "theme_name": "unknown",
                    "created_at": datetime.now().isoformat(),
                    "metadata": {},
                    "analytics": {},
                }

            if "manual_feedback" not in data[video_id]:
                data[video_id]["manual_feedback"] = []

            data[video_id]["manual_feedback"].append(
                {
                    "positive": positive,
                    "comment": comment,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            with open(self.feedback_file, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

            # テーマにフィードバックを反映
            theme_name = data[video_id]["theme_name"]
            if theme_name != "unknown":
                self.theme_manager.record_feedback(theme_name, positive)

            logger.info(f"Recorded manual feedback for video {video_id}: {'positive' if positive else 'negative'}")

        except Exception as e:
            logger.error(f"Failed to record manual feedback: {e}")

    def record_ai_review(self, video_id: str, review: VideoReviewResult):
        """AIによる動画レビュー結果を保存"""
        try:
            with open(self.feedback_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            if video_id not in data:
                data[video_id] = {
                    "theme_name": "unknown",
                    "created_at": datetime.now().isoformat(),
                    "metadata": {},
                    "analytics": {},
                }

            ai_review_entry = review.to_dict()
            ai_review_entry["stored_at"] = datetime.now().isoformat()

            history = data[video_id].setdefault("ai_review_history", [])
            history.append(ai_review_entry)
            data[video_id]["ai_review"] = ai_review_entry

            with open(self.feedback_file, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

            logger.info("Recorded AI review feedback for video %s", video_id)
        except Exception as e:
            logger.error(f"Failed to record AI review: {e}")

    def get_video_feedback(self, video_id: str) -> Optional[Dict]:
        """特定動画のフィードバックを取得"""
        try:
            with open(self.feedback_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                if isinstance(data, dict):
                    return data.get(video_id)
        except Exception as e:
            logger.error(f"Failed to get video feedback: {e}")
            return None

    def get_theme_performance_summary(self, theme_name: str) -> Dict:
        """特定テーマのパフォーマンスサマリーを取得"""
        try:
            with open(self.feedback_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            theme_videos = [v for v in data.values() if v.get("theme_name") == theme_name]

            if not theme_videos:
                return {
                    "theme_name": theme_name,
                    "video_count": 0,
                    "total_views": 0,
                    "total_likes": 0,
                    "avg_retention_rate": 0.0,
                    "avg_view_duration": 0.0,
                    "positive_feedback_count": 0,
                    "negative_feedback_count": 0,
                }

            total_views = sum(v.get("analytics", {}).get("views", 0) for v in theme_videos)
            total_likes = sum(v.get("analytics", {}).get("likes", 0) for v in theme_videos)
            retention_rates = [
                v.get("analytics", {}).get("retention_rate", 0) for v in theme_videos if v.get("analytics")
            ]
            view_durations = [
                v.get("analytics", {}).get("avg_view_duration", 0) for v in theme_videos if v.get("analytics")
            ]

            positive_count = 0
            negative_count = 0
            for v in theme_videos:
                for fb in v.get("manual_feedback", []):
                    if fb["positive"]:
                        positive_count += 1
                    else:
                        negative_count += 1

            return {
                "theme_name": theme_name,
                "video_count": len(theme_videos),
                "total_views": total_views,
                "total_likes": total_likes,
                "avg_retention_rate": sum(retention_rates) / len(retention_rates) if retention_rates else 0.0,
                "avg_view_duration": sum(view_durations) / len(view_durations) if view_durations else 0.0,
                "positive_feedback_count": positive_count,
                "negative_feedback_count": negative_count,
            }

        except Exception as e:
            logger.error(f"Failed to get theme performance summary: {e}")
            return {}

    def print_performance_report(self):
        """全テーマのパフォーマンスレポートを出力"""
        print("\n" + "=" * 70)
        print("背景テーマ パフォーマンスレポート（実動画データ）")
        print("=" * 70)

        themes = self.theme_manager.themes.keys()
        for theme_name in themes:
            summary = self.get_theme_performance_summary(theme_name)
            if summary.get("video_count", 0) == 0:
                continue

            print(f"\nテーマ: {theme_name}")
            print(f"  動画数: {summary['video_count']}")
            print(f"  総視聴数: {summary['total_views']:,}")
            print(f"  総いいね数: {summary['total_likes']:,}")
            print(f"  平均視聴維持率: {summary['avg_retention_rate']:.1f}%")
            print(f"  平均視聴時間: {summary['avg_view_duration']:.0f}秒")
            print(f"  ポジティブフィードバック: {summary['positive_feedback_count']}")
            print(f"  ネガティブフィードバック: {summary['negative_feedback_count']}")

        print("\n" + "=" * 70)


# グローバルインスタンス
feedback_collector = VideoFeedbackCollector()


def get_feedback_collector() -> VideoFeedbackCollector:
    """フィードバックコレクターを取得"""
    return feedback_collector


if __name__ == "__main__":
    # テストコード
    collector = VideoFeedbackCollector()

    # テストデータ
    test_video_id = "test_video_123"
    collector.record_video_metadata(test_video_id, "professional_blue", {"title": "Test Video", "duration": 300})

    # アナリティクス更新（シミュレーション）
    collector.update_analytics(
        test_video_id,
        {
            "views": 1000,
            "likes": 80,
            "dislikes": 5,
            "comments": 15,
            "avg_view_duration": 240.5,
            "avg_view_percentage": 80.2,
            "retention_rate": 75.5,
            "click_through_rate": 12.3,
        },
    )

    # 手動フィードバック
    collector.record_manual_feedback(test_video_id, positive=True, comment="Great visuals!")
    collector.record_manual_feedback(test_video_id, positive=True, comment="Love the background")

    # レポート出力
    collector.print_performance_report()

    # テーママネージャーのレポートも出力
    get_theme_manager().print_analytics_report()
