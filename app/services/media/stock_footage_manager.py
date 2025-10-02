"""Stock footage management using free APIs (Pexels, Pixabay).

無料のストックビデオAPIを使用して、ニュースコンテンツに合った
プロフェッショナルなB-roll映像を自動取得します。
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional
import requests
from datetime import datetime

logger = logging.getLogger(__name__)


class StockFootageManager:
    """Free stock footage manager using Pexels and Pixabay APIs."""

    PEXELS_API_URL = "https://api.pexels.com/videos/search"
    PIXABAY_API_URL = "https://pixabay.com/api/videos/"

    def __init__(self, pexels_api_key: str = "", pixabay_api_key: str = ""):
        """Initialize stock footage manager.

        Args:
            pexels_api_key: Pexels API key (free from https://www.pexels.com/api/)
            pixabay_api_key: Pixabay API key (free from https://pixabay.com/api/docs/)
        """
        self.pexels_api_key = pexels_api_key or os.getenv("PEXELS_API_KEY", "")
        self.pixabay_api_key = pixabay_api_key or os.getenv("PIXABAY_API_KEY", "")
        self.cache_dir = Path(tempfile.gettempdir()) / "stock_footage_cache"
        self.cache_dir.mkdir(exist_ok=True)

        if not self.pexels_api_key and not self.pixabay_api_key:
            logger.warning("No stock footage API keys configured. Get free keys from:")
            logger.warning("  - Pexels: https://www.pexels.com/api/")
            logger.warning("  - Pixabay: https://pixabay.com/api/docs/")

    def search_footage(
        self,
        keywords: List[str],
        duration_target: float = 10.0,
        max_clips: int = 5,
        orientation: str = "landscape",
    ) -> List[Dict]:
        """Search for stock footage matching keywords.

        Args:
            keywords: List of search keywords (English)
            duration_target: Target total duration in seconds
            max_clips: Maximum number of clips to retrieve
            orientation: Video orientation (landscape/portrait/square)

        Returns:
            List of video metadata dicts with url, duration, etc.
        """
        all_results = []

        # Try Pexels first (better quality, more reliable)
        if self.pexels_api_key:
            pexels_results = self._search_pexels(keywords, max_clips, orientation)
            all_results.extend(pexels_results)
            logger.info(f"Found {len(pexels_results)} clips from Pexels")

        # Fallback to Pixabay if needed
        if len(all_results) < max_clips and self.pixabay_api_key:
            pixabay_results = self._search_pixabay(
                keywords, max_clips - len(all_results), orientation
            )
            all_results.extend(pixabay_results)
            logger.info(f"Found {len(pixabay_results)} clips from Pixabay")

        if not all_results:
            logger.warning(f"No stock footage found for keywords: {keywords}")
            return []

        # Sort by relevance and quality
        all_results.sort(key=lambda x: (x.get("quality", 0), x.get("duration", 0)), reverse=True)

        # Limit to max_clips
        return all_results[:max_clips]

    def _search_pexels(
        self, keywords: List[str], max_clips: int, orientation: str
    ) -> List[Dict]:
        """Search Pexels API for stock footage."""
        results = []

        for keyword in keywords[:3]:  # Limit to 3 keywords to avoid rate limits
            try:
                response = requests.get(
                    self.PEXELS_API_URL,
                    headers={"Authorization": self.pexels_api_key},
                    params={
                        "query": keyword,
                        "per_page": max(3, max_clips // len(keywords)),
                        "orientation": orientation,
                        "size": "medium",
                    },
                    timeout=10,
                )

                if response.status_code == 200:
                    data = response.json()
                    videos = data.get("videos", [])

                    for video in videos:
                        video_files = video.get("video_files", [])
                        if not video_files:
                            continue

                        # Get best quality HD file
                        hd_file = self._get_best_video_file(video_files)

                        if hd_file:
                            results.append({
                                "id": f"pexels_{video['id']}",
                                "url": hd_file["link"],
                                "duration": video.get("duration", 10),
                                "keyword": keyword,
                                "width": video.get("width", 1920),
                                "height": video.get("height", 1080),
                                "quality": hd_file.get("quality", "hd"),
                                "source": "pexels",
                                "thumbnail": video.get("image", ""),
                            })

                elif response.status_code == 429:
                    logger.warning("Pexels API rate limit reached")
                    break
                else:
                    logger.warning(f"Pexels API error {response.status_code}: {response.text}")

            except Exception as e:
                logger.error(f"Error searching Pexels for '{keyword}': {e}")

        return results

    def _search_pixabay(
        self, keywords: List[str], max_clips: int, orientation: str
    ) -> List[Dict]:
        """Search Pixabay API for stock footage."""
        results = []

        for keyword in keywords[:3]:
            try:
                response = requests.get(
                    self.PIXABAY_API_URL,
                    params={
                        "key": self.pixabay_api_key,
                        "q": keyword,
                        "per_page": max(3, max_clips // len(keywords)),
                        "video_type": "all",
                    },
                    timeout=10,
                )

                if response.status_code == 200:
                    data = response.json()
                    videos = data.get("hits", [])

                    for video in videos:
                        # Get medium quality video
                        video_url = video.get("videos", {}).get("medium", {}).get("url")

                        if video_url:
                            results.append({
                                "id": f"pixabay_{video['id']}",
                                "url": video_url,
                                "duration": video.get("duration", 10),
                                "keyword": keyword,
                                "width": video.get("videos", {}).get("medium", {}).get("width", 1280),
                                "height": video.get("videos", {}).get("medium", {}).get("height", 720),
                                "quality": "medium",
                                "source": "pixabay",
                                "thumbnail": video.get("picture_id", ""),
                            })

                else:
                    logger.warning(f"Pixabay API error {response.status_code}")

            except Exception as e:
                logger.error(f"Error searching Pixabay for '{keyword}': {e}")

        return results

    def _get_best_video_file(self, video_files: List[Dict]) -> Optional[Dict]:
        """Select best quality video file from Pexels response."""
        # Priority: hd > sd > original
        quality_priority = ["hd", "sd"]

        for quality in quality_priority:
            for file in video_files:
                if file.get("quality") == quality and file.get("width", 0) >= 1280:
                    return file

        # Fallback to first file
        return video_files[0] if video_files else None

    def download_clip(self, video_metadata: Dict, output_dir: Optional[Path] = None) -> Optional[str]:
        """Download stock video clip to local storage.

        Args:
            video_metadata: Video metadata dict from search_footage()
            output_dir: Output directory (uses temp cache if not specified)

        Returns:
            Local file path of downloaded video, or None if failed
        """
        if not video_metadata.get("url"):
            logger.error("No URL in video metadata")
            return None

        output_dir = output_dir or self.cache_dir
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True, parents=True)

        video_id = video_metadata.get("id", f"video_{datetime.now().strftime('%Y%m%d%H%M%S')}")
        output_path = output_dir / f"{video_id}.mp4"

        # Check cache
        if output_path.exists():
            logger.info(f"Using cached video: {output_path}")
            return str(output_path)

        # Download
        try:
            logger.info(f"Downloading stock footage: {video_metadata['keyword']} from {video_metadata['source']}")
            response = requests.get(video_metadata["url"], stream=True, timeout=60)
            response.raise_for_status()

            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            logger.info(f"Downloaded: {output_path} ({file_size_mb:.1f} MB)")
            return str(output_path)

        except Exception as e:
            logger.error(f"Failed to download video: {e}")
            if output_path.exists():
                output_path.unlink()
            return None

    def download_clips(self, video_list: List[Dict], max_parallel: int = 3) -> List[str]:
        """Download multiple clips (sequential for simplicity).

        Args:
            video_list: List of video metadata dicts
            max_parallel: Maximum concurrent downloads (not yet implemented)

        Returns:
            List of local file paths
        """
        downloaded = []

        for video in video_list:
            path = self.download_clip(video)
            if path:
                downloaded.append(path)

        logger.info(f"Downloaded {len(downloaded)}/{len(video_list)} clips successfully")
        return downloaded

    def clear_cache(self, older_than_days: int = 7):
        """Clear old cached videos.

        Args:
            older_than_days: Delete files older than this many days
        """
        if not self.cache_dir.exists():
            return

        import time
        now = time.time()
        cutoff = older_than_days * 24 * 3600
        deleted = 0

        for file_path in self.cache_dir.glob("*.mp4"):
            if now - file_path.stat().st_mtime > cutoff:
                try:
                    file_path.unlink()
                    deleted += 1
                except Exception as e:
                    logger.warning(f"Failed to delete {file_path}: {e}")

        if deleted > 0:
            logger.info(f"Cleared {deleted} cached videos older than {older_than_days} days")


if __name__ == "__main__":
    # Test with sample keywords
    manager = StockFootageManager()

    keywords = ["economy", "finance", "stock market"]
    print(f"\nSearching for stock footage: {keywords}")

    results = manager.search_footage(keywords, max_clips=3)
    print(f"Found {len(results)} clips:")

    for i, video in enumerate(results, 1):
        print(f"\n{i}. {video['keyword']} ({video['source']})")
        print(f"   Duration: {video['duration']}s")
        print(f"   Quality: {video['quality']} ({video['width']}x{video['height']})")
        print(f"   URL: {video['url'][:60]}...")

    if results:
        print("\nDownloading first clip...")
        path = manager.download_clip(results[0])
        if path:
            print(f"✓ Downloaded to: {path}")
