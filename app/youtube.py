"""YouTube操作モジュール

YouTube Data API v3を使用して動画のアップロード、
メタデータ設定、公開管理を行います。
"""

import json
import logging
import os
import pickle
from datetime import datetime
from typing import Any, Dict, List

import httplib2
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from app.config import cfg

logger = logging.getLogger(__name__)


class YouTubeManager:
    """YouTube API管理クラス"""

    # OAuth 2.0 スコープ
    SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]

    def __init__(self):
        self.service = None
        self.credentials = None
        self.client_secrets = cfg.youtube_client_secret
        self._setup_service()

    def _setup_service(self):
        """YouTube API サービスを初期化"""
        try:
            if not self.client_secrets:
                raise ValueError(
                    "YouTube client secrets not configured or invalid. Please check YOUTUBE_CLIENT_SECRET environment variable."
                )

            # 認証情報を取得
            self.credentials = self._get_authenticated_credentials()

            if not self.credentials:
                raise ValueError("Failed to obtain YouTube credentials")

            # YouTube API サービスを構築
            self.service = build("youtube", "v3", credentials=self.credentials)

            logger.info("YouTube API service initialized")

        except Exception as e:
            logger.error(f"Failed to initialize YouTube service: {e}")
            raise

    def _get_authenticated_credentials(self) -> Credentials:
        """認証済み認証情報を取得"""
        creds = None
        token_file = "token.pickle"

        # 既存のトークンファイルをチェック
        if os.path.exists(token_file):
            with open(token_file, "rb") as token:
                creds = pickle.load(token)

        # 認証情報が無効または存在しない場合
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    logger.info("Refreshed YouTube credentials")
                except Exception as e:
                    logger.warning(f"Failed to refresh credentials: {e}")
                    creds = None

            if not creds:
                # 新しい認証フローを実行
                creds = self._run_oauth_flow()

            # 認証情報を保存
            if creds:
                with open(token_file, "wb") as token:
                    pickle.dump(creds, token)

        return creds

    def _run_oauth_flow(self) -> Credentials:
        """OAuth認証フローを実行"""
        try:
            # クライアント設定を準備
            if isinstance(self.client_secrets, str):
                if self.client_secrets.startswith("{"):
                    # JSON文字列の場合
                    client_config = json.loads(self.client_secrets)
                else:
                    # ファイルパスの場合
                    with open(self.client_secrets, "r") as f:
                        client_config = json.load(f)
            else:
                client_config = self.client_secrets
            logger.debug(f"YouTube client_config: {client_config}")

            if not client_config:
                raise ValueError("YouTube client secrets are missing or invalid for OAuth flow.")

            if not client_config:
                raise ValueError("YouTube client secrets are missing or invalid for OAuth flow.")

            # OAuth フローを作成
            flow = InstalledAppFlow.from_client_config(client_config, self.SCOPES)

            # ローカルサーバーで認証実行
            creds = flow.run_local_server(port=0)

            logger.info("Completed YouTube OAuth flow")
            return creds

        except Exception as e:
            logger.error(f"OAuth flow failed: {e}")
            return None

    def upload_video(
        self, video_path: str, metadata: Dict[str, Any], thumbnail_path: str = None, privacy_status: str = "private"
    ) -> Dict[str, Any]:
        """動画をYouTubeにアップロード

        Args:
            video_path: 動画ファイルのパス
            metadata: 動画メタデータ
            thumbnail_path: サムネイル画像のパス
            privacy_status: 公開設定 (private/unlisted/public)

        Returns:
            アップロード結果の情報

        """
        try:
            if not os.path.exists(video_path):
                raise FileNotFoundError(f"Video file not found: {video_path}")

            # アップロード情報を準備
            upload_info = self._prepare_upload_metadata(metadata, privacy_status)

            # ファイルサイズを確認
            file_size = os.path.getsize(video_path)
            logger.info(f"Uploading video: {video_path} ({file_size} bytes)")

            # メディアアップロードを準備
            media = MediaFileUpload(
                video_path,
                chunksize=-1,  # 一括アップロード
                resumable=True,
            )

            # アップロードリクエストを作成
            insert_request = self.service.videos().insert(
                part=",".join(upload_info.keys()), body=upload_info, media_body=media
            )

            # アップロード実行
            video_response = self._execute_upload(insert_request)

            if not video_response:
                raise Exception("Video upload failed")

            video_id = video_response.get("id")
            logger.info(f"Video uploaded successfully: {video_id}")

            # サムネイルをアップロード
            thumbnail_result = None
            if thumbnail_path and os.path.exists(thumbnail_path):
                thumbnail_result = self._upload_thumbnail(video_id, thumbnail_path)

            # 結果を整理
            result = {
                "video_id": video_id,
                "title": upload_info["snippet"]["title"],
                "description": upload_info["snippet"]["description"],
                "video_url": f"https://www.youtube.com/watch?v={video_id}",
                "privacy_status": privacy_status,
                "uploaded_at": datetime.now().isoformat(),
                "file_size": file_size,
                "thumbnail_uploaded": thumbnail_result is not None,
            }

            if thumbnail_result:
                result["thumbnail_result"] = thumbnail_result

            return result

        except Exception as e:
            logger.error(f"Video upload failed: {e}")
            return {"error": str(e), "video_path": video_path, "upload_failed_at": datetime.now().isoformat()}

    def _prepare_upload_metadata(self, metadata: Dict[str, Any], privacy_status: str) -> Dict[str, Any]:
        """アップロード用メタデータを準備"""
        # タイトルと説明文を準備
        title = str(metadata.get("title", "Untitled Video"))[:100]  # YouTube制限
        description = str(metadata.get("description", ""))[:5000]  # YouTube制限

        # タグを準備
        tags = metadata.get("tags", [])
        if isinstance(tags, list):
            # タグの長さ制限とクリーニング
            clean_tags = []
            for tag in tags[:30]:  # 最大30個
                clean_tag = str(tag).strip()
                if clean_tag and len(clean_tag) <= 100:
                    clean_tags.append(clean_tag)
            tags = clean_tags

        # カテゴリIDを取得
        category_id = self._get_category_id(metadata.get("category", "News & Politics"))

        upload_body = {
            "snippet": {"title": title, "description": description, "tags": tags, "categoryId": category_id},
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,  # 子供向けコンテンツではない
            },
        }

        return upload_body

    def _get_category_id(self, category_name: str) -> str:
        """カテゴリ名からYouTubeカテゴリIDを取得"""
        category_mapping = {
            "News & Politics": "25",
            "Education": "27",
            "Business": "25",  # News & Politics に分類
            "Finance": "25",  # News & Politics に分類
            "Economics": "25",  # News & Politics に分類
            "Entertainment": "24",
            "Technology": "28",
            "Science": "28",
        }

        return category_mapping.get(category_name, "25")  # デフォルト: News & Politics

    def _execute_upload(self, insert_request) -> Dict[str, Any]:
        """アップロードを実行（リトライ機能付き）"""
        import random
        import time

        max_retries = 3
        retriable_exceptions = (httplib2.HttpLib2Error, IOError, HttpError)

        for retry in range(max_retries):
            try:
                response = insert_request.execute()
                return response

            except HttpError as e:
                if e.resp.status in [500, 502, 503, 504]:
                    # サーバーエラーの場合はリトライ
                    wait_time = (2**retry) + random.uniform(0, 1)
                    logger.warning(f"Server error {e.resp.status}, retrying in {wait_time:.2f}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    # クライアントエラーの場合はリトライしない
                    logger.error(f"HTTP error {e.resp.status}: {e}")
                    raise

            except retriable_exceptions as e:
                wait_time = (2**retry) + random.uniform(0, 1)
                logger.warning(f"Retriable error, waiting {wait_time:.2f}s: {e}")
                time.sleep(wait_time)
                continue

            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                raise

        raise Exception("Max retries exceeded for video upload")

    def _upload_thumbnail(self, video_id: str, thumbnail_path: str) -> Dict[str, Any]:
        """サムネイル画像をアップロード"""
        try:
            self.service.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(thumbnail_path)).execute()

            logger.info(f"Thumbnail uploaded for video: {video_id}")
            return {"uploaded": True, "thumbnail_path": thumbnail_path, "uploaded_at": datetime.now().isoformat()}

        except Exception as e:
            logger.error(f"Thumbnail upload failed for {video_id}: {e}")
            return {"uploaded": False, "error": str(e), "thumbnail_path": thumbnail_path}

    def update_video(self, video_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """動画情報を更新"""
        try:
            # 現在の動画情報を取得
            current_video = self.service.videos().list(part="snippet,status", id=video_id).execute()

            if not current_video.get("items"):
                raise ValueError(f"Video not found: {video_id}")

            video_info = current_video["items"][0]

            # 更新データを準備
            update_body = {"id": video_id, "snippet": video_info["snippet"], "status": video_info["status"]}

            # 更新項目を適用
            if "title" in updates:
                update_body["snippet"]["title"] = str(updates["title"])[:100]

            if "description" in updates:
                update_body["snippet"]["description"] = str(updates["description"])[:5000]

            if "tags" in updates:
                update_body["snippet"]["tags"] = updates["tags"][:30]

            if "privacy_status" in updates:
                update_body["status"]["privacyStatus"] = updates["privacy_status"]

            # 更新実行
            response = self.service.videos().update(part="snippet,status", body=update_body).execute()

            logger.info(f"Video updated: {video_id}")
            return {"updated": True, "video_id": video_id, "updated_at": datetime.now().isoformat()}

        except Exception as e:
            logger.error(f"Video update failed for {video_id}: {e}")
            return {"updated": False, "error": str(e), "video_id": video_id}

    def get_video_info(self, video_id: str) -> Dict[str, Any]:
        """動画情報を取得"""
        try:
            response = self.service.videos().list(part="snippet,status,statistics", id=video_id).execute()

            if not response.get("items"):
                raise ValueError(f"Video not found: {video_id}")

            video_data = response["items"][0]

            video_info = {
                "video_id": video_id,
                "title": video_data["snippet"]["title"],
                "description": video_data["snippet"]["description"],
                "published_at": video_data["snippet"]["publishedAt"],
                "privacy_status": video_data["status"]["privacyStatus"],
                "view_count": int(video_data["statistics"].get("viewCount", 0)),
                "like_count": int(video_data["statistics"].get("likeCount", 0)),
                "comment_count": int(video_data["statistics"].get("commentCount", 0)),
                "video_url": f"https://www.youtube.com/watch?v={video_id}",
            }

            return video_info

        except Exception as e:
            logger.error(f"Failed to get video info for {video_id}: {e}")
            return {"error": str(e), "video_id": video_id}

    def list_channel_videos(self, max_results: int = 50) -> List[Dict[str, Any]]:
        """チャンネルの動画一覧を取得"""
        try:
            # チャンネル情報を取得
            channel_response = self.service.channels().list(part="contentDetails", mine=True).execute()

            if not channel_response.get("items"):
                raise ValueError("No channel found for authenticated user")

            uploads_playlist_id = channel_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

            # アップロード動画一覧を取得
            playlist_response = (
                self.service.playlistItems()
                .list(part="snippet", playlistId=uploads_playlist_id, maxResults=max_results)
                .execute()
            )

            videos = []
            for item in playlist_response.get("items", []):
                video_info = {
                    "video_id": item["snippet"]["resourceId"]["videoId"],
                    "title": item["snippet"]["title"],
                    "published_at": item["snippet"]["publishedAt"],
                    "video_url": f"https://www.youtube.com/watch?v={item['snippet']['resourceId']['videoId']}",
                }
                videos.append(video_info)

            logger.info(f"Retrieved {len(videos)} channel videos")
            return videos

        except Exception as e:
            logger.error(f"Failed to list channel videos: {e}")
            return []

    def schedule_video(self, video_id: str, publish_time: datetime) -> Dict[str, Any]:
        """動画の公開スケジュールを設定"""
        try:
            # ISO形式の時刻文字列に変換
            scheduled_time = publish_time.isoformat() + "Z"

            update_body = {
                "id": video_id,
                "status": {
                    "privacyStatus": "private",  # スケジュール設定時はprivate
                    "publishAt": scheduled_time,
                },
            }

            response = self.service.videos().update(part="status", body=update_body).execute()

            logger.info(f"Video scheduled for {publish_time}: {video_id}")
            return {"scheduled": True, "video_id": video_id, "publish_time": scheduled_time}

        except Exception as e:
            logger.error(f"Failed to schedule video {video_id}: {e}")
            return {"scheduled": False, "error": str(e), "video_id": video_id}

    def get_upload_quota(self) -> Dict[str, Any]:
        """アップロード制限情報を取得"""
        try:
            # YouTube APIの制限情報を取得
            # 実際の制限は動的に変更されるため、推定値を返す
            quota_info = {
                "daily_upload_limit_mb": 128 * 1024,  # 128GB (推定)
                "max_video_length_hours": 12,
                "max_file_size_mb": 256 * 1024,  # 256GB (推定)
                "estimated_remaining_quota": "Unknown",  # APIでは正確な残量は取得できない
                "reset_time": "Daily at midnight PT",
            }

            return quota_info

        except Exception as e:
            logger.error(f"Failed to get upload quota: {e}")
            return {"error": str(e)}


# グローバルインスタンス
youtube_manager = YouTubeManager() if cfg.youtube_client_secret else None


def upload_video(
    video_path: str, metadata: Dict[str, Any], thumbnail_path: str = None, privacy_status: str = "private"
) -> Dict[str, Any]:
    """動画アップロードの簡易関数"""
    if youtube_manager:
        return youtube_manager.upload_video(video_path, metadata, thumbnail_path, privacy_status)
    else:
        logger.warning("YouTube manager not available")
        return {"error": "YouTube manager not configured"}


def update_video(video_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """動画更新の簡易関数"""
    if youtube_manager:
        return youtube_manager.update_video(video_id, updates)
    else:
        logger.warning("YouTube manager not available")
        return {"error": "YouTube manager not configured"}


def get_video_info(video_id: str) -> Dict[str, Any]:
    """動画情報取得の簡易関数"""
    if youtube_manager:
        return youtube_manager.get_video_info(video_id)
    else:
        logger.warning("YouTube manager not available")
        return {"error": "YouTube manager not configured"}


if __name__ == "__main__":
    # テスト実行
    print("Testing YouTube functionality...")

    # 設定確認
    print(f"YouTube client secrets configured: {bool(cfg.youtube_client_secret)}")

    if cfg.youtube_client_secret:
        try:
            manager = YouTubeManager()

            # アップロード制限情報
            print("\n=== Upload Quota Information ===")
            quota_info = manager.get_upload_quota()
            print(f"Daily upload limit: {quota_info.get('daily_upload_limit_mb', 0)} MB")
            print(f"Max video length: {quota_info.get('max_video_length_hours', 0)} hours")

            # チャンネル動画一覧取得テスト
            print("\n=== Recent Channel Videos ===")
            videos = manager.list_channel_videos(max_results=5)
            for video in videos[:3]:
                print(f"  {video['title']} ({video['video_id']})")

            # テスト用メタデータ
            test_metadata = {
                "title": "テスト動画 - 経済ニュース解説",
                "description": "これはテスト用の動画アップロードです。\n\n#テスト #経済ニュース",
                "tags": ["テスト", "経済ニュース", "解説"],
                "category": "News & Politics",
            }

            print("\n=== Test Metadata ===")
            print(f"Title: {test_metadata['title']}")
            print(f"Tags: {test_metadata['tags']}")

            # 実際のアップロードテストは動画ファイルが必要
            test_video_files = ["output_video.mp4", "test.mp4", "sample.mp4"]
            test_video_path = None

            for video_file in test_video_files:
                if os.path.exists(video_file):
                    test_video_path = video_file
                    break

            if test_video_path:
                print("\n=== Test Video Upload (DRY RUN) ===")
                print(f"Would upload: {test_video_path}")
                file_size = os.path.getsize(test_video_path)
                print(f"File size: {file_size} bytes")
                print("Note: Actual upload test skipped to avoid unnecessary uploads")

                # 実際のアップロードをテストする場合は以下のコメントを外す
                # result = manager.upload_video(test_video_path, test_metadata, privacy_status="private")
                # if 'video_id' in result:
                #     print(f"Upload successful: {result['video_id']}")
                #     print(f"URL: {result['video_url']}")
                # else:
                #     print(f"Upload failed: {result.get('error', 'Unknown error')}")
            else:
                print("No test video files found for upload test")

        except Exception as e:
            print(f"Test failed: {e}")
            if "oauth" in str(e).lower():
                print("Note: OAuth setup required for YouTube access")
                print("Run the application normally to complete authentication")
    else:
        print("YouTube client secrets not configured, skipping tests")

    print("\nYouTube API test completed.")
