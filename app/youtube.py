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
from app.config.settings import settings
logger = logging.getLogger(__name__)
class YouTubeManager:
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube', 'https://www.googleapis.com/auth/youtube.force-ssl']
    def __init__(self):
        self.service = None
        self.credentials = None
        self.client_secrets = settings.api_keys.get('youtube')
        self._setup_service()
    def _setup_service(self):
        try:
            if not self.client_secrets:
                raise ValueError('YouTube client secrets not configured or invalid. Please check YOUTUBE_CLIENT_SECRET environment variable.')
            self.credentials = self._get_authenticated_credentials()
            if not self.credentials:
                raise ValueError('Failed to obtain YouTube credentials')
            self.service = build('youtube', 'v3', credentials=self.credentials)
            logger.info('YouTube API service initialized')
        except Exception as e:
            logger.error(f'Failed to initialize YouTube service: {e}')
            raise
    def _get_authenticated_credentials(self) -> Credentials:
        creds = None
        token_file = 'token.pickle'
        if os.path.exists(token_file):
            with open(token_file, 'rb') as token:
                creds = pickle.load(token)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    logger.info('Refreshed YouTube credentials')
                except Exception as e:
                    logger.warning(f'Failed to refresh credentials: {e}')
                    creds = None
            if not creds:
                creds = self._run_oauth_flow()
            if creds:
                with open(token_file, 'wb') as token:
                    pickle.dump(creds, token)
        return creds
    def _run_oauth_flow(self) -> Credentials:
        try:
            if isinstance(self.client_secrets, str):
                if self.client_secrets.startswith('{'):
                    client_config = json.loads(self.client_secrets)
                else:
                    if not os.path.exists(self.client_secrets):
                        raise FileNotFoundError(f'OAuth client file not found: {self.client_secrets}')
                    with open(self.client_secrets, 'r') as f:
                        client_config = json.load(f)
            else:
                client_config = self.client_secrets
            if not client_config:
                raise ValueError('YouTube client secrets are missing or invalid for OAuth flow.')
            if client_config.get('type') == 'service_account':
                raise ValueError('Service account credentials cannot be used for YouTube uploads. You need OAuth 2.0 Client ID (Desktop app). Run: uv run python setup_youtube_oauth.py for setup instructions.')
            flow = InstalledAppFlow.from_client_config(client_config, self.SCOPES)
            logger.info('Opening browser for YouTube OAuth authentication...')
            logger.info('Please sign in and grant permissions in your browser.')
            creds = flow.run_local_server(port=8080)
            logger.info('✅ YouTube OAuth authentication completed successfully!')
            return creds
        except Exception as e:
            logger.error(f'OAuth flow failed: {e}')
            return None
    def upload_video(self, video_path: str, metadata: Dict[str, Any], thumbnail_path: str=None, subtitle_path: str=None, privacy_status: str='private') -> Dict[str, Any]:
        try:
            if not os.path.exists(video_path):
                raise FileNotFoundError(f'Video file not found: {video_path}')
            upload_info = self._prepare_upload_metadata(metadata, privacy_status)
            file_size = os.path.getsize(video_path)
            logger.info(f'Uploading video: {video_path} ({file_size} bytes)')
            media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
            insert_request = self.service.videos().insert(part=','.join(upload_info.keys()), body=upload_info, media_body=media)
            video_response = self._execute_upload(insert_request)
            if not video_response:
                raise Exception('Video upload failed')
            video_id = video_response.get('id')
            logger.info(f'Video uploaded successfully: {video_id}')
            thumbnail_result = None
            if thumbnail_path and os.path.exists(thumbnail_path):
                thumbnail_result = self._upload_thumbnail(video_id, thumbnail_path)
            caption_result = None
            if subtitle_path and os.path.exists(subtitle_path):
                caption_result = self._upload_caption(video_id, subtitle_path)
            result = {'video_id': video_id, 'title': upload_info['snippet']['title'], 'description': upload_info['snippet']['description'], 'video_url': f'https://www.youtube.com/watch?v={video_id}', 'privacy_status': privacy_status, 'uploaded_at': datetime.now().isoformat(), 'file_size': file_size, 'thumbnail_uploaded': thumbnail_result is not None, 'caption_uploaded': caption_result is not None}
            if thumbnail_result:
                result['thumbnail_result'] = thumbnail_result
            if caption_result:
                result['caption_result'] = caption_result
            return result
        except Exception as e:
            logger.error(f'Video upload failed: {e}')
            return {'error': str(e), 'video_path': video_path, 'upload_failed_at': datetime.now().isoformat()}
    def _prepare_upload_metadata(self, metadata: Dict[str, Any], privacy_status: str) -> Dict[str, Any]:
        title = str(metadata.get('title', 'Untitled Video'))[:100]
        description = str(metadata.get('description', ''))[:5000]
        tags = metadata.get('tags', [])
        if isinstance(tags, list):
            clean_tags = []
            for tag in tags[:30]:
                clean_tag = str(tag).strip()
                if clean_tag and len(clean_tag) <= 100:
                    clean_tags.append(clean_tag)
            tags = clean_tags
        category_id = self._get_category_id(metadata.get('category', 'News & Politics'))
        upload_body = {'snippet': {'title': title, 'description': description, 'tags': tags, 'categoryId': category_id}, 'status': {'privacyStatus': privacy_status, 'selfDeclaredMadeForKids': False}}
        return upload_body
    def _get_category_id(self, category_name: str) -> str:
        category_mapping = {'News & Politics': '25', 'Education': '27', 'Business': '25', 'Finance': '25', 'Economics': '25', 'Entertainment': '24', 'Technology': '28', 'Science': '28'}
        return category_mapping.get(category_name, '25')
    def _execute_upload(self, insert_request) -> Dict[str, Any]:
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
                    wait_time = 2 ** retry + random.uniform(0, 1)
                    logger.warning(f'Server error {e.resp.status}, retrying in {wait_time:.2f}s...')
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f'HTTP error {e.resp.status}: {e}')
                    raise
            except retriable_exceptions as e:
                wait_time = 2 ** retry + random.uniform(0, 1)
                logger.warning(f'Retriable error, waiting {wait_time:.2f}s: {e}')
                time.sleep(wait_time)
                continue
            except Exception as e:
                logger.error(f'Unexpected error: {e}')
                raise
        raise Exception('Max retries exceeded for video upload')
    def _upload_thumbnail(self, video_id: str, thumbnail_path: str) -> Dict[str, Any]:
        try:
            request = self.service.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(thumbnail_path, mimetype='image/png'))
            request.execute()
            logger.info(f'Thumbnail uploaded for video: {video_id}')
            return {'uploaded': True, 'thumbnail_path': thumbnail_path, 'uploaded_at': datetime.now().isoformat()}
        except HttpError as e:
            error_detail = str(e)
            if e.resp.status == 403 and ('forbidden' in error_detail.lower() or 'not be properly authorized' in error_detail):
                logger.warning(f'Thumbnail upload not authorized for video {video_id}. This may be due to OAuth scope limitations. Video upload was successful. You can manually set the thumbnail in YouTube Studio.')
                return {'uploaded': False, 'skipped': True, 'reason': 'authorization_insufficient', 'error': 'OAuth scope may not include thumbnail permissions', 'thumbnail_path': thumbnail_path}
            logger.error(f'Thumbnail upload failed for {video_id}: {e}')
            return {'uploaded': False, 'error': str(e), 'thumbnail_path': thumbnail_path}
        except Exception as e:
            logger.error(f'Thumbnail upload failed for {video_id}: {e}')
            return {'uploaded': False, 'error': str(e), 'thumbnail_path': thumbnail_path}
    def _upload_caption(self, video_id: str, subtitle_path: str, language: str='ja') -> Dict[str, Any]:
        try:
            caption_body = {'snippet': {'videoId': video_id, 'language': language, 'name': 'Japanese' if language == 'ja' else language, 'isDraft': False}}
            media = MediaFileUpload(subtitle_path, mimetype='application/octet-stream', resumable=True)
            request = self.service.captions().insert(part='snippet', body=caption_body, media_body=media, sync=False)
            response = request.execute()
            logger.info(f'Caption uploaded for video: {video_id} (language: {language})')
            return {'uploaded': True, 'caption_id': response.get('id'), 'language': language, 'subtitle_path': subtitle_path, 'uploaded_at': datetime.now().isoformat()}
        except HttpError as e:
            if e.resp.status == 403:
                logger.warning(f'Caption upload not authorized for video {video_id}. This may be due to OAuth scope limitations. Video upload was successful. You can manually add captions in YouTube Studio.')
                return {'uploaded': False, 'skipped': True, 'reason': 'authorization_insufficient', 'error': 'OAuth scope may not include caption permissions', 'subtitle_path': subtitle_path}
            logger.error(f'Caption upload failed for {video_id}: {e}')
            return {'uploaded': False, 'error': str(e), 'subtitle_path': subtitle_path}
        except Exception as e:
            logger.error(f'Caption upload failed for {video_id}: {e}')
            return {'uploaded': False, 'error': str(e), 'subtitle_path': subtitle_path}
    def update_video(self, video_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        try:
            current_video = self.service.videos().list(part='snippet,status', id=video_id).execute()
            if not current_video.get('items'):
                raise ValueError(f'Video not found: {video_id}')
            video_info = current_video['items'][0]
            update_body = {'id': video_id, 'snippet': video_info['snippet'], 'status': video_info['status']}
            if 'title' in updates:
                update_body['snippet']['title'] = str(updates['title'])[:100]
            if 'description' in updates:
                update_body['snippet']['description'] = str(updates['description'])[:5000]
            if 'tags' in updates:
                update_body['snippet']['tags'] = updates['tags'][:30]
            if 'privacy_status' in updates:
                update_body['status']['privacyStatus'] = updates['privacy_status']
            self.service.videos().update(part='snippet,status', body=update_body).execute()
            logger.info(f'Video updated: {video_id}')
            return {'updated': True, 'video_id': video_id, 'updated_at': datetime.now().isoformat()}
        except Exception as e:
            logger.error(f'Video update failed for {video_id}: {e}')
            return {'updated': False, 'error': str(e), 'video_id': video_id}
    def get_video_info(self, video_id: str) -> Dict[str, Any]:
        try:
            response = self.service.videos().list(part='snippet,status,statistics', id=video_id).execute()
            if not response.get('items'):
                raise ValueError(f'Video not found: {video_id}')
            video_data = response['items'][0]
            video_info = {'video_id': video_id, 'title': video_data['snippet']['title'], 'description': video_data['snippet']['description'], 'published_at': video_data['snippet']['publishedAt'], 'privacy_status': video_data['status']['privacyStatus'], 'view_count': int(video_data['statistics'].get('viewCount', 0)), 'like_count': int(video_data['statistics'].get('likeCount', 0)), 'comment_count': int(video_data['statistics'].get('commentCount', 0)), 'video_url': f'https://www.youtube.com/watch?v={video_id}'}
            return video_info
        except Exception as e:
            logger.error(f'Failed to get video info for {video_id}: {e}')
            return {'error': str(e), 'video_id': video_id}
    def list_channel_videos(self, max_results: int=50) -> List[Dict[str, Any]]:
        try:
            channel_response = self.service.channels().list(part='contentDetails', mine=True).execute()
            if not channel_response.get('items'):
                raise ValueError('No channel found for authenticated user')
            uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            playlist_response = self.service.playlistItems().list(part='snippet', playlistId=uploads_playlist_id, maxResults=max_results).execute()
            videos = []
            for item in playlist_response.get('items', []):
                video_info = {'video_id': item['snippet']['resourceId']['videoId'], 'title': item['snippet']['title'], 'published_at': item['snippet']['publishedAt'], 'video_url': f"https://www.youtube.com/watch?v={item['snippet']['resourceId']['videoId']}"}
                videos.append(video_info)
            logger.info(f'Retrieved {len(videos)} channel videos')
            return videos
        except Exception as e:
            logger.error(f'Failed to list channel videos: {e}')
            return []
    def schedule_video(self, video_id: str, publish_time: datetime) -> Dict[str, Any]:
        try:
            scheduled_time = publish_time.isoformat() + 'Z'
            update_body = {'id': video_id, 'status': {'privacyStatus': 'private', 'publishAt': scheduled_time}}
            self.service.videos().update(part='status', body=update_body).execute()
            logger.info(f'Video scheduled for {publish_time}: {video_id}')
            return {'scheduled': True, 'video_id': video_id, 'publish_time': scheduled_time}
        except Exception as e:
            logger.error(f'Failed to schedule video {video_id}: {e}')
            return {'scheduled': False, 'error': str(e), 'video_id': video_id}
    def get_upload_quota(self) -> Dict[str, Any]:
        try:
            quota_info = {'daily_upload_limit_mb': 128 * 1024, 'max_video_length_hours': 12, 'max_file_size_mb': 256 * 1024, 'estimated_remaining_quota': 'Unknown', 'reset_time': 'Daily at midnight PT'}
            return quota_info
        except Exception as e:
            logger.error(f'Failed to get upload quota: {e}')
            return {'error': str(e)}
youtube_manager = YouTubeManager() if settings.api_keys.get('youtube') else None
def upload_video(video_path: str, metadata: Dict[str, Any], thumbnail_path: str=None, subtitle_path: str=None, privacy_status: str='private') -> Dict[str, Any]:
    if youtube_manager:
        return youtube_manager.upload_video(video_path, metadata, thumbnail_path, subtitle_path, privacy_status)
    else:
        logger.warning('YouTube manager not available')
        return {'error': 'YouTube manager not configured'}
def update_video(video_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    if youtube_manager:
        return youtube_manager.update_video(video_id, updates)
    else:
        logger.warning('YouTube manager not available')
        return {'error': 'YouTube manager not configured'}
def get_video_info(video_id: str) -> Dict[str, Any]:
    if youtube_manager:
        return youtube_manager.get_video_info(video_id)
    else:
        logger.warning('YouTube manager not available')
        return {'error': 'YouTube manager not configured'}
if __name__ == '__main__':
    print('Testing YouTube functionality...')
    print(f'YouTube client secrets configured: {bool(settings.youtube_client_secret)}')
    if settings.youtube_client_secret:
        try:
            manager = YouTubeManager()
            print('\n=== Upload Quota Information ===')
            quota_info = manager.get_upload_quota()
            print(f"Daily upload limit: {quota_info.get('daily_upload_limit_mb', 0)} MB")
            print(f"Max video length: {quota_info.get('max_video_length_hours', 0)} hours")
            print('\n=== Recent Channel Videos ===')
            videos = manager.list_channel_videos(max_results=5)
            for video in videos[:3]:
                print(f"  {video['title']} ({video['video_id']})")
            test_metadata = {'title': 'テスト動画 - 経済ニュース解説', 'description': 'これはテスト用の動画アップロードです。\n\n
            print('\n=== Test Metadata ===')
            print(f"Title: {test_metadata['title']}")
            print(f"Tags: {test_metadata['tags']}")
            test_video_files = ['output_video.mp4', 'test.mp4', 'sample.mp4']
            test_video_path = None
            for video_file in test_video_files:
                if os.path.exists(video_file):
                    test_video_path = video_file
                    break
            if test_video_path:
                print('\n=== Test Video Upload (DRY RUN) ===')
                print(f'Would upload: {test_video_path}')
                file_size = os.path.getsize(test_video_path)
                print(f'File size: {file_size} bytes')
                print('Note: Actual upload test skipped to avoid unnecessary uploads')
            else:
                print('No test video files found for upload test')
        except Exception as e:
            print(f'Test failed: {e}')
            if 'oauth' in str(e).lower():
                print('Note: OAuth setup required for YouTube access')
                print('Run the application normally to complete authentication')
    else:
        print('YouTube client secrets not configured, skipping tests')
    print('\nYouTube API test completed.')