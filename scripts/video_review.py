#!/usr/bin/env python3
"""生成済み動画をレビューして次の制作サイクルに活かすCLI"""

import argparse
import json
import logging
from pathlib import Path
from typing import Dict, Optional

from app.services.video_review import get_video_review_service

logger = logging.getLogger(__name__)


def _load_metadata(path: Optional[str]) -> Dict[str, str]:
    if not path:
        return {}
    metadata_path = Path(path)
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {path}")
    with metadata_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("Metadata JSON must be an object")
        return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="動画レビューAIを実行してフィードバックを取得する")
    parser.add_argument("videos", nargs="+", help="レビューする動画ファイルパス")
    parser.add_argument("--video-id", help="YouTube動画IDなどの識別子（単一動画時のみ）")
    parser.add_argument("--metadata-json", help="タイトル等を含むJSONパス")
    parser.add_argument("--title", help="動画タイトル（オプション）")
    parser.add_argument("--duration", help="動画尺のメモ（例: 8分12秒）")
    parser.add_argument("--force", action="store_true", help="既存スクリーンショットを再生成する")
    parser.add_argument("--json", action="store_true", help="結果をJSONで出力する")
    return parser


def main():
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    parser = build_parser()
    args = parser.parse_args()

    if len(args.videos) > 1 and args.video_id:
        parser.error("--video-id は単一動画のときのみ指定できます")

    base_metadata = _load_metadata(args.metadata_json)
    if args.title:
        base_metadata["title"] = args.title
    if args.duration:
        base_metadata["duration"] = args.duration

    service = get_video_review_service()

    for video in args.videos:
        video_path = Path(video)
        if not video_path.exists():
            logger.error("Video not found: %s", video)
            continue

        video_id = args.video_id if len(args.videos) == 1 else None

        logger.info("Reviewing video: %s", video_path)
        result = service.review_video(
            video_path=str(video_path),
            video_id=video_id,
            metadata=base_metadata or None,
            force_capture=args.force,
        )

        feedback = result.feedback
        if args.json:
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
            continue

        print("\n" + "=" * 60)
        heading = f"レビュー結果: {video_path.name}"
        print(heading)
        print("=" * len(heading))
        if feedback:
            print(f"要約: {feedback.summary}")
            if feedback.positive_highlights:
                print("\n◎ 良かった点")
                for item in feedback.positive_highlights:
                    print(f"  - {item}")
            if feedback.improvement_suggestions:
                print("\n△ 改善提案")
                for item in feedback.improvement_suggestions:
                    print(f"  - {item}")
            if feedback.retention_risks:
                print("\n⚠ 離脱リスク")
                for item in feedback.retention_risks:
                    print(f"  - {item}")
            if feedback.next_video_actions:
                print("\n▶ 次の動画で試すこと")
                for item in feedback.next_video_actions:
                    print(f"  - {item}")
        else:
            print("フィードバックが取得できませんでした")

        if result.screenshots:
            screenshot_dir = Path(result.screenshots[0].path).parent
            print(f"\nスクリーンショット保存先: {screenshot_dir}")


if __name__ == "__main__":  # pragma: no cover
    main()
