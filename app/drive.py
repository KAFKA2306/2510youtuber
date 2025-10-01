"""Google Drive操作モジュール

生成した動画ファイルをGoogle Driveにアップロードし、
共有リンクを生成してファイル管理を行います。
"""

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import cfg

logger = logging.getLogger(__name__)


class DriveManager:
    """Google Drive管理クラス"""

    def __init__(self):
        self.service = None
        self.folder_id = cfg.google_drive_folder_id
        self.credentials = cfg.google_credentials_json
        self._setup_service()

    def _setup_service(self):
        """Google Drive APIサービスを初期化"""
        try:
            if not self.credentials:
                raise ValueError("Google credentials not configured")

            # 認証情報を設定
            if isinstance(self.credentials, dict):
                credentials = Credentials.from_service_account_info(
                    self.credentials, scopes=["https://www.googleapis.com/auth/drive"]
                )
            elif isinstance(self.credentials, str) and os.path.exists(self.credentials):
                credentials = Credentials.from_service_account_file(
                    self.credentials, scopes=["https://www.googleapis.com/auth/drive"]
                )
            else:
                raise ValueError(f"Invalid credentials format or path: {self.credentials}")

            # Drive APIサービスを構築
            self.service = build("drive", "v3", credentials=credentials)

            # フォルダの存在確認
            if self.folder_id:
                self._verify_folder_access()

            logger.info("Google Drive service initialized")

        except Exception as e:
            logger.error(f"Failed to initialize Google Drive service: {e}")
            raise

    def _verify_folder_access(self):
        """指定フォルダへのアクセス権限を確認"""
        try:
            folder_info = self.service.files().get(fileId=self.folder_id, fields="id,name,mimeType").execute()

            if folder_info.get("mimeType") != "application/vnd.google-apps.folder":
                raise ValueError(f"Specified ID is not a folder: {self.folder_id}")

            logger.info(f"Verified access to folder: {folder_info.get('name')}")

        except Exception as e:
            logger.warning(f"Could not verify folder access: {e}")

    def upload_file(
        self, file_path: str, folder_id: str = None, custom_name: str = None, make_public: bool = True
    ) -> Dict[str, Any]:
        """ファイルをGoogle Driveにアップロード"""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            file_size = os.path.getsize(file_path)
            file_name = custom_name or os.path.basename(file_path)

            logger.info(f"Uploading file: {file_name} ({file_size} bytes)")

            target_folder_id = folder_id or self.folder_id

            file_metadata = {"name": file_name}

            if target_folder_id:
                file_metadata["parents"] = [target_folder_id]

            mime_type = self._get_mime_type(file_path)

            media = MediaFileUpload(
                file_path, mimetype=mime_type, resumable=True if file_size > 5 * 1024 * 1024 else False
            )

            file_result = (
                self.service.files()
                .create(body=file_metadata, media_body=media, fields="id,name,size,webViewLink,webContentLink")
                .execute()
            )

            if make_public:
                self._make_file_public(file_result.get("id"))

            upload_info = {
                "file_id": file_result.get("id"),
                "name": file_result.get("name"),
                "size": int(file_result.get("size", 0)),
                "web_view_link": file_result.get("webViewLink"),
                "web_content_link": file_result.get("webContentLink"),
                "folder_id": target_folder_id,
                "uploaded_at": datetime.now().isoformat(),
                "public": make_public,
            }

            logger.info(f"File uploaded successfully: {upload_info['file_id']}")
            return upload_info

        except Exception as e:
            logger.error(f"File upload failed: {e}")
            return self._get_upload_error_info(file_path, str(e))

    def _get_mime_type(self, file_path: str) -> str:
        import mimetypes

        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type:
            return mime_type
        ext = Path(file_path).suffix.lower()
        mime_mappings = {
            ".mp4": "video/mp4",
            ".avi": "video/x-msvideo",
            ".mov": "video/quicktime",
            ".wav": "audio/wav",
            ".mp3": "audio/mpeg",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".srt": "text/plain",
            ".txt": "text/plain",
            ".json": "application/json",
        }
        return mime_mappings.get(ext, "application/octet-stream")

    def _make_file_public(self, file_id: str):
        try:
            permission = {"type": "anyone", "role": "reader"}
            self.service.permissions().create(fileId=file_id, body=permission).execute()
            logger.debug(f"Made file public: {file_id}")
        except Exception as e:
            logger.warning(f"Failed to make file public: {e}")

    def upload_video_package(
        self, video_path: str, thumbnail_path: str = None, subtitle_path: str = None, metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        try:
            package_folder_id = self._create_package_folder(metadata)
            upload_results = {"package_folder_id": package_folder_id, "uploaded_files": [], "errors": []}
            if video_path and os.path.exists(video_path):
                video_result = self.upload_file(
                    video_path,
                    folder_id=package_folder_id,
                    custom_name=f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4",
                )
                upload_results["uploaded_files"].append({"type": "video", "result": video_result})
                upload_results["video_file_id"] = video_result.get("file_id")
                upload_results["video_link"] = video_result.get("web_view_link")
            if thumbnail_path and os.path.exists(thumbnail_path):
                thumbnail_result = self.upload_file(
                    thumbnail_path,
                    folder_id=package_folder_id,
                    custom_name=f"thumbnail_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                )
                upload_results["uploaded_files"].append({"type": "thumbnail", "result": thumbnail_result})
                upload_results["thumbnail_file_id"] = thumbnail_result.get("file_id")
            if subtitle_path and os.path.exists(subtitle_path):
                subtitle_result = self.upload_file(
                    subtitle_path,
                    folder_id=package_folder_id,
                    custom_name=f"subtitles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.srt",
                )
                upload_results["uploaded_files"].append({"type": "subtitle", "result": subtitle_result})
                upload_results["subtitle_file_id"] = subtitle_result.get("file_id")
            if metadata:
                metadata_path = self._create_metadata_file(metadata, package_folder_id)
                if metadata_path:
                    metadata_result = self.upload_file(
                        metadata_path, folder_id=package_folder_id, custom_name="metadata.json"
                    )
                    upload_results["uploaded_files"].append({"type": "metadata", "result": metadata_result})
                    try:
                        os.remove(metadata_path)
                    except Exception:
                        pass
            upload_results["package_folder_link"] = self._get_folder_link(package_folder_id)
            upload_results["upload_completed_at"] = datetime.now().isoformat()
            logger.info(f"Video package uploaded to folder: {package_folder_id}")
            return upload_results
        except Exception as e:
            logger.error(f"Video package upload failed: {e}")
            return {"error": str(e), "uploaded_files": [], "upload_failed_at": datetime.now().isoformat()}

    def _create_package_folder(self, metadata: Dict[str, Any] = None) -> str:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            title = metadata.get("title", "Untitled") if metadata else "Untitled"
            safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip()
            folder_name = f"{timestamp}_{safe_title[:30]}"
            folder_metadata = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
            if self.folder_id:
                folder_metadata["parents"] = [self.folder_id]
            folder_result = self.service.files().create(body=folder_metadata, fields="id,name").execute()
            folder_id = folder_result.get("id")
            logger.info(f"Created package folder: {folder_name} ({folder_id})")
            return folder_id
        except Exception as e:
            logger.error(f"Failed to create package folder: {e}")
            return self.folder_id

    def _create_metadata_file(self, metadata: Dict[str, Any], folder_id: str) -> str:
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
                temp_path = f.name
            logger.debug(f"Created metadata file: {temp_path}")
            return temp_path
        except Exception as e:
            logger.error(f"Failed to create metadata file: {e}")
            return None

    def _get_folder_link(self, folder_id: str) -> str:
        try:
            folder_info = self.service.files().get(fileId=folder_id, fields="webViewLink").execute()
            return folder_info.get("webViewLink", "")
        except Exception as e:
            logger.warning(f"Failed to get folder link: {e}")
            return f"https://drive.google.com/drive/folders/{folder_id}"

    def _get_upload_error_info(self, file_path: str, error_msg: str) -> Dict[str, Any]:
        return {
            "error": error_msg,
            "file_path": file_path,
            "file_exists": os.path.exists(file_path),
            "file_size": os.path.getsize(file_path) if os.path.exists(file_path) else 0,
            "upload_failed_at": datetime.now().isoformat(),
        }

    def list_files(self, folder_id: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            target_folder_id = folder_id or self.folder_id
            query = f"'{target_folder_id}' in parents and trashed=false" if target_folder_id else "trashed=false"
            results = (
                self.service.files()
                .list(q=query, pageSize=limit, fields="files(id,name,size,mimeType,createdTime,webViewLink)")
                .execute()
            )
            files = results.get("files", [])
            file_list = []
            for file_info in files:
                file_list.append(
                    {
                        "id": file_info.get("id"),
                        "name": file_info.get("name"),
                        "size": int(file_info.get("size", 0)),
                        "mime_type": file_info.get("mimeType"),
                        "created_time": file_info.get("createdTime"),
                        "web_view_link": file_info.get("webViewLink"),
                    }
                )
            logger.info(f"Listed {len(file_list)} files from folder: {target_folder_id}")
            return file_list
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return []

    def delete_file(self, file_id: str) -> bool:
        try:
            self.service.files().delete(fileId=file_id).execute()
            logger.info(f"Deleted file: {file_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete file {file_id}: {e}")
            return False

    def cleanup_old_files(self, days_old: int = 30) -> int:
        try:
            from datetime import timedelta

            cutoff_date = datetime.now() - timedelta(days=days_old)
            cutoff_str = cutoff_date.isoformat()
            query = f"createdTime < '{cutoff_str}' and trashed=false"
            if self.folder_id:
                query += f" and '{self.folder_id}' in parents"
            results = self.service.files().list(q=query, fields="files(id,name,createdTime)").execute()
            old_files = results.get("files", [])
            deleted_count = 0
            for file_info in old_files:
                if self.delete_file(file_info.get("id")):
                    deleted_count += 1
            logger.info(f"Cleaned up {deleted_count} old files (older than {days_old} days)")
            return deleted_count
        except Exception as e:
            logger.error(f"Failed to cleanup old files: {e}")
            return 0

    def get_storage_usage(self) -> Dict[str, Any]:
        try:
            about_info = self.service.about().get(fields="storageQuota").execute()
            storage_quota = about_info.get("storageQuota", {})
            usage_info = {
                "limit_gb": int(storage_quota.get("limit", 0)) / (1024**3),
                "usage_gb": int(storage_quota.get("usage", 0)) / (1024**3),
                "usage_in_drive_gb": int(storage_quota.get("usageInDrive", 0)) / (1024**3),
                "usage_in_drive_trash_gb": int(storage_quota.get("usageInDriveTrash", 0)) / (1024**3),
            }
            usage_info["available_gb"] = usage_info["limit_gb"] - usage_info["usage_gb"]
            usage_info["usage_percentage"] = (usage_info["usage_gb"] / usage_info["limit_gb"]) * 100
            return usage_info
        except Exception as e:
            logger.error(f"Failed to get storage usage: {e}")
            return {}


# グローバルインスタンス
drive_manager = DriveManager() if cfg.google_credentials_json else None


def upload_file(file_path: str, folder_id: str = None, make_public: bool = True) -> Dict[str, Any]:
    if drive_manager:
        return drive_manager.upload_file(file_path, folder_id, make_public=make_public)
    else:
        logger.warning("Drive manager not available")
        return {"error": "Drive manager not configured"}


def upload_video_package(
    video_path: str, thumbnail_path: str = None, subtitle_path: str = None, metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    if drive_manager:
        return drive_manager.upload_video_package(video_path, thumbnail_path, subtitle_path, metadata)
    else:
        logger.warning("Drive manager not available")
        return {"error": "Drive manager not configured"}


if __name__ == "__main__":
    print("Testing Google Drive functionality...")
    if cfg.google_credentials_json:
        try:
            manager = DriveManager()
            print("\n=== Storage Usage ===")
            usage = manager.get_storage_usage()
            if usage:
                print(f"Total: {usage.get('limit_gb', 0):.1f} GB")
                print(f"Used: {usage.get('usage_gb', 0):.1f} GB ({usage.get('usage_percentage', 0):.1f}%)")
                print(f"Available: {usage.get('available_gb', 0):.1f} GB")
            print("\n=== Recent Files ===")
            files = manager.list_files(limit=5)
            for file_info in files[:3]:
                print(f"  {file_info['name']} ({file_info['size']} bytes)")
            test_files = ["output_audio.wav", "thumbnail.png", "subtitles.srt"]
            for test_file in test_files:
                if os.path.exists(test_file):
                    print(f"\n=== Testing upload: {test_file} ===")
                    result = manager.upload_file(test_file, make_public=True)
                    if "file_id" in result:
                        print(f"Uploaded: {result['file_id']}")
                        print(f"Link: {result.get('web_view_link', 'N/A')}")
                        if manager.delete_file(result["file_id"]):
                            print(f"Test file deleted: {result['file_id']}")
                    else:
                        print(f"Upload failed: {result.get('error', 'Unknown error')}")
                    break
        except Exception as e:
            print(f"Test failed: {e}")
    else:
        print("Google Drive credentials not configured, skipping tests")

    print("\nGoogle Drive test completed.")
