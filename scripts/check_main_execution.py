#!/usr/bin/env python3
"""
メイン実行の成功/失敗をチェックするスクリプト
GitHub Actionsのバックアップ実行判定に使用
"""

import sys
import datetime
from app.sheets import sheets


def check_recent_execution():
    """直近の実行が成功したかチェック"""
    try:
        # 過去2時間以内の実行をチェック
        cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=2)

        # スプレッドシートから最新の実行記録を取得
        recent_runs = sheets.get_recent_runs(cutoff_time)

        if not recent_runs:
            print("No recent executions found")
            return 1  # 失敗扱い

        latest_run = recent_runs[0]

        if latest_run['status'] == 'completed':
            print(f"Main execution succeeded: {latest_run['run_id']}")
            return 0  # 成功
        else:
            print(f"Main execution failed: {latest_run['run_id']} - {latest_run['status']}")
            return 1  # 失敗

    except Exception as e:
        print(f"Check failed: {e}")
        return 1  # エラーは失敗扱い


if __name__ == "__main__":
    exit_code = check_recent_execution()
    sys.exit(exit_code)
