#!/usr/bin/env python3
"""
ログファイルを解析して統計情報を表示
"""

import re
from collections import defaultdict
from pathlib import Path


def analyze_log(log_file):
    """ログファイルを解析"""

    stats = {
        "steps": [],
        "agents": defaultdict(lambda: {"success": 0, "failed": 0}),
        "api_calls": defaultdict(int),
        "errors": [],
        "durations": {},
    }

    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            # ステップ検出
            if "▶ STEP:" in line:
                step = line.split("STEP:")[1].strip()
                stats["steps"].append(step)

            # エージェント検出
            if "🤖 Agent" in line:
                match = re.search(r"Agent \[(.+?)\]", line)
                if match:
                    agent = match.group(1)
                    if "✅" in line:
                        stats["agents"][agent]["success"] += 1
                    elif "❌" in line:
                        stats["agents"][agent]["failed"] += 1

            # API呼び出し
            if "🌐 API" in line:
                match = re.search(r"API \[(.+?)\]", line)
                if match:
                    stats["api_calls"][match.group(1)] += 1

            # エラー検出
            if "ERROR" in line:
                stats["errors"].append(line.strip())

            # 所要時間
            if "completed (" in line:
                match = re.search(r"(.+?) completed \((.+?)s\)", line)
                if match:
                    stats["durations"][match.group(1)] = float(match.group(2))

    return stats


def print_summary(stats):
    """統計サマリーを表示"""
    print("\n" + "=" * 60)
    print("📊 LOG ANALYSIS SUMMARY")
    print("=" * 60)

    print(f"\n✅ Steps executed: {len(stats['steps'])}")
    for step in stats["steps"]:
        duration = stats["durations"].get(step, 0)
        print(f"  - {step}: {duration:.2f}s")

    print("\n🤖 Agents:")
    for agent, counts in stats["agents"].items():
        total = counts["success"] + counts["failed"]
        print(f"  - {agent}: {counts['success']}/{total} succeeded")

    print(f"\n🌐 API Calls: {sum(stats['api_calls'].values())} total")
    for api, count in stats["api_calls"].items():
        print(f"  - {api}: {count} calls")

    print(f"\n❌ Errors: {len(stats['errors'])}")
    for error in stats["errors"][:5]:  # 最初の5件のみ
        print(f"  - {error[:80]}...")


if __name__ == "__main__":
    import sys

    log_file = sys.argv[1] if len(sys.argv) > 1 else sorted(Path("logs").glob("workflow_*.log"))[-1]
    stats = analyze_log(log_file)
    print_summary(stats)
