#!/usr/bin/env python3
"""Analytics report CLI tool.

Usage:
  python scripts/analytics_report.py           # Weekly report
  python scripts/analytics_report.py --hooks   # Hook performance
  python scripts/analytics_report.py --topics  # Topic distribution
"""

import argparse
import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.analytics import analyzer


def main():
    parser = argparse.ArgumentParser(description="Generate analytics reports")
    parser.add_argument("--hooks", action="store_true", help="Show hook performance")
    parser.add_argument("--topics", action="store_true", help="Show topic distribution")
    parser.add_argument("--limit", type=int, default=50, help="Number of executions to analyze")

    args = parser.parse_args()

    if args.hooks:
        print("🎯 Hook Strategy Performance\n")
        hook_perf = analyzer.analyze_hook_performance()
        for hook, stats in hook_perf.items():
            print(f"{hook}:")
            print(f"  動画数: {stats['count']}")
            print(f"  平均WOW: {stats['avg_wow']:.2f}")
            print(f"  平均リテンション: {stats['avg_retention']:.1f}%")
            print()

    elif args.topics:
        print("📚 Topic Distribution\n")
        topics = analyzer.analyze_topic_distribution()
        for topic, count in topics.items():
            print(f"  {topic}: {count} 本")
        print()

    else:
        # Default: weekly report
        print(analyzer.generate_weekly_report())


if __name__ == "__main__":
    main()
