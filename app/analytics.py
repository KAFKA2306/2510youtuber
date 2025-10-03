"""フィードバックループ分析モジュール.

JSONL実行ログから統計を分析し、継続的改善のためのインサイトを提供します。
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from app.metadata_storage import metadata_storage
from app.models.workflow import WorkflowResult

logger = logging.getLogger(__name__)


class FeedbackAnalyzer:
    """フィードバックデータ分析クラス."""

    def __init__(self, jsonl_path: Optional[str] = None):
        self.jsonl_path = jsonl_path or metadata_storage.jsonl_path

    def load_executions(self, limit: int = 100) -> List[WorkflowResult]:
        """JSONL from execution log を読み込み."""
        executions = []

        try:
            if not Path(self.jsonl_path).exists():
                logger.warning(f"Execution log not found: {self.jsonl_path}")
                return []

            with open(self.jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        result = WorkflowResult(**data)
                        executions.append(result)
                    except Exception as e:
                        logger.debug(f"Failed to parse line: {e}")
                        continue

                    if len(executions) >= limit:
                        break

            logger.info(f"Loaded {len(executions)} execution records")
            return executions

        except Exception as e:
            logger.error(f"Failed to load executions: {e}")
            return []

    def analyze_hook_performance(self) -> Dict[str, Dict[str, float]]:
        """フック戦略ごとのパフォーマンスを分析."""
        executions = self.load_executions()
        if not executions:
            return {}

        hook_stats = {}

        for ex in executions:
            hook = ex.hook_type or "その他"
            if hook not in hook_stats:
                hook_stats[hook] = {"count": 0, "total_wow": 0.0, "total_retention": 0.0}

            hook_stats[hook]["count"] += 1
            if ex.wow_score:
                hook_stats[hook]["total_wow"] += ex.wow_score
            if ex.retention_prediction:
                hook_stats[hook]["total_retention"] += ex.retention_prediction

        # Calculate averages
        for hook, stats in hook_stats.items():
            count = stats["count"]
            stats["avg_wow"] = stats["total_wow"] / count if count > 0 else 0
            stats["avg_retention"] = stats["total_retention"] / count if count > 0 else 0

        return hook_stats

    def analyze_topic_distribution(self) -> Dict[str, int]:
        """トピック別の動画数を分析."""
        executions = self.load_executions()
        topic_count = {}

        for ex in executions:
            topic = ex.topic or "一般"
            topic_count[topic] = topic_count.get(topic, 0) + 1

        return dict(sorted(topic_count.items(), key=lambda x: x[1], reverse=True))

    def get_best_performing_videos(self, limit: int = 10) -> List[WorkflowResult]:
        """WOWスコアでトップの動画を取得."""
        executions = self.load_executions()
        with_wow = [ex for ex in executions if ex.wow_score is not None]
        sorted_execs = sorted(with_wow, key=lambda x: x.wow_score, reverse=True)
        return sorted_execs[:limit]

    def calculate_success_rate(self) -> float:
        """成功率を計算（%）."""
        executions = self.load_executions()
        if not executions:
            return 0.0

        successful = sum(1 for ex in executions if ex.success)
        return (successful / len(executions)) * 100

    def generate_weekly_report(self) -> str:
        """週次レポートを生成."""
        executions = self.load_executions(limit=50)
        recent = executions[:7]  # Last 7

        if not recent:
            return "No execution data available."

        avg_wow = sum(ex.wow_score for ex in recent if ex.wow_score) / len([ex for ex in recent if ex.wow_score])
        success_rate = self.calculate_success_rate()
        hook_performance = self.analyze_hook_performance()

        report = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 週次パフォーマンスレポート
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 全体統計
  • 実行回数: {len(recent)} 回
  • 成功率: {success_rate:.1f}%
  • 平均WOWスコア: {avg_wow:.2f}/10.0

🎯 フック戦略パフォーマンス
"""

        for hook, stats in hook_performance.items():
            report += f"  • {hook}: {stats['count']}本 (平均WOW {stats['avg_wow']:.1f}, リテンション {stats['avg_retention']:.1f}%)\n"

        best_videos = self.get_best_performing_videos(limit=3)
        if best_videos:
            report += "\n🏆 トップパフォーマンス動画\n"
            for i, video in enumerate(best_videos, 1):
                report += f"  {i}. {video.title or 'N/A'} (WOW {video.wow_score:.1f})\n"

        report += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

        return report


# Global instance
analyzer = FeedbackAnalyzer()


if __name__ == "__main__":
    # Test analytics
    print("📊 Feedback Analytics\n")

    print("Loading execution data...")
    executions = analyzer.load_executions(limit=10)
    print(f"Loaded {len(executions)} executions\n")

    if executions:
        print("Hook Performance:")
        hook_perf = analyzer.analyze_hook_performance()
        for hook, stats in hook_perf.items():
            print(f"  {hook}: {stats['count']} videos, avg WOW {stats['avg_wow']:.1f}")

        print("\nTopic Distribution:")
        topics = analyzer.analyze_topic_distribution()
        for topic, count in topics.items():
            print(f"  {topic}: {count} videos")

        print("\n" + "=" * 50)
        print(analyzer.generate_weekly_report())
    else:
        print("No execution data found. Run the workflow first.")
