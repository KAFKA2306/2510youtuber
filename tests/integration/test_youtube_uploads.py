import json
import os
import sys
from typing import Dict, List

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

# Configure logging
import logging

from app.config import cfg
from app.youtube import YouTubeManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_failed_upload_videos(output_dir: str) -> List[Dict[str, str]]:
    """
    outputディレクトリからアップロードに失敗した動画のパスとメタデータを取得します。
    video_idまたはvideo_urlがmetadata.jsonに存在しないものを失敗とみなします。
    """
    failed_videos = []
    for entry in os.listdir(output_dir):
        full_path = os.path.join(output_dir, entry)
        if os.path.isdir(full_path):
            metadata_path = os.path.join(full_path, "metadata.json")
            video_path = os.path.join(full_path, "video.mp4")

            if os.path.exists(metadata_path) and os.path.exists(video_path):
                try:
                    with open(metadata_path, "r", encoding="utf-8") as f:
                        metadata = json.load(f)

                    # video_idまたはvideo_urlが存在しない場合、失敗とみなす
                    if "video_id" not in metadata and "video_url" not in metadata:
                        failed_videos.append(
                            {
                                "video_path": video_path,
                                "metadata": metadata,
                                "thumbnail_path": os.path.join(full_path, "thumbnail.png")
                                if os.path.exists(os.path.join(full_path, "thumbnail.png"))
                                else None,
                            }
                        )
                except json.JSONDecodeError as e:
                    logger.error(f"Error decoding JSON from {metadata_path}: {e}")
                except Exception as e:
                    logger.error(f"Error processing {metadata_path}: {e}")
    return failed_videos


pytestmark = [pytest.mark.integration, pytest.mark.youtube]


@pytest.mark.asyncio
@pytest.mark.requires_api_key
async def test_youtube_uploads():
    """
    outputディレクトリ内のアップロード失敗動画を再アップロードするテストを実行します。
    """
    logger.info("Starting YouTube re-upload test...")

    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "output"))
    if not os.path.exists(output_dir):
        logger.error(f"Output directory not found: {output_dir}")
        return

    failed_videos = get_failed_upload_videos(output_dir)

    if not failed_videos:
        logger.info("No failed upload videos found in the output directory.")
        return

    logger.info(f"Found {len(failed_videos)} failed upload videos to re-test.")

    if not cfg.youtube_client_secret:
        logger.error(
            "YouTube client secrets not configured. Please set YOUTUBE_CLIENT_SECRET in config.py or environment."
        )
        return

    # cfg.youtube_client_secret は既に辞書として解析されているため、os.path.exists() は不要
    logger.info(
        f"YOUTUBE_CLIENT_SECRET (from cfg): {cfg.youtube_client_secret.get('installed', {}).get('client_id', 'N/A')[:20]}..."
    )

    try:
        manager = YouTubeManager()
    except Exception as e:
        logger.error(f"Failed to initialize YouTubeManager: {e}")
        return

    for i, video_info in enumerate(failed_videos):
        video_path = video_info["video_path"]
        metadata = video_info["metadata"]
        thumbnail_path = video_info["thumbnail_path"]

        logger.info(f"[{i+1}/{len(failed_videos)}] Attempting to re-upload: {video_path}")
        logger.info(f"  Title: {metadata.get('title', 'N/A')}")

        # privacy_statusをprivateに設定してテストアップロード
        upload_result = manager.upload_video(
            video_path=video_path, metadata=metadata, thumbnail_path=thumbnail_path, privacy_status="private"
        )

        if upload_result.get("video_id"):
            logger.info(
                f"  ✅ Re-upload successful! Video ID: {upload_result['video_id']}, URL: {upload_result['video_url']}"
            )
            # 成功した場合、metadata.jsonを更新することも検討できるが、ここではテストに留める
        else:
            logger.error(f"  ❌ Re-upload failed for {video_path}: {upload_result.get('error', 'Unknown error')}")

    logger.info("YouTube re-upload test completed.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_youtube_uploads())
