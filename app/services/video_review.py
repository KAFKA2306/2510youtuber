"""動画レビューAIサービス

生成済み・投稿済み動画を1分ごとのスクリーンショットで分析し、
次の動画制作に活かすフィードバックを生成する。
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import ffmpeg
import google.generativeai as genai

from app.core.api_rotation import get_rotation_manager
from app.config.settings import settings
from app.models.video_review import (
    ScreenshotEvidence,
    VideoReviewFeedback,
    VideoReviewResult,
)
from app.core.utils import FileUtils
from app.media.video_feedback import get_feedback_collector

logger = logging.getLogger(__name__)


class ScreenshotExtractionError(Exception):
    """スクリーンショット抽出に失敗したときの例外"""


class VideoScreenshotExtractor:
    """FFmpegを用いた動画スクリーンショット抽出ユーティリティ"""

    def __init__(self, ffmpeg_path: Optional[str] = None):
        self.ffmpeg_path = ffmpeg_path or settings.ffmpeg_path

    def extract(
        self,
        video_path: str,
        output_dir: str,
        interval_seconds: int,
        max_screenshots: int,
        force: bool = False,
    ) -> List[ScreenshotEvidence]:
        """動画から一定間隔でスクリーンショットを抽出"""
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        if max_screenshots <= 0:
            raise ValueError("max_screenshots must be positive")
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")

        FileUtils.ensure_directory(output_dir)

        existing = sorted(Path(output_dir).glob("*.png"))
        duration = self._get_video_duration(video_path)
        expected_count = max(1, min(max_screenshots, math.ceil(duration / interval_seconds)))

        if existing and not force:
            logger.info(
                "Reusing %d existing screenshots in %s (expected %d)",
                len(existing),
                output_dir,
                expected_count,
            )
            return self._build_metadata(existing[:expected_count], interval_seconds, duration)

        for png in existing:
            try:
                png.unlink()
            except OSError:
                logger.debug("Failed to remove old screenshot: %s", png)

        output_pattern = os.path.join(output_dir, "shot_%03d.png")
        logger.info(
            "Extracting screenshots from %s every %ss (max %d) into %s",
            video_path,
            interval_seconds,
            max_screenshots,
            output_dir,
        )

        try:
            (
                ffmpeg.input(video_path)
                .filter_("fps", fps=f"1/{interval_seconds}")
                .output(
                    output_pattern,
                    vsync="vfr",
                    vframes=max_screenshots,
                )
                .overwrite_output()
            ).run(cmd=[self.ffmpeg_path], quiet=True)
        except ffmpeg.Error as exc:  # type: ignore[attr-defined]
            logger.error("FFmpeg error during screenshot extraction: %s", exc)
            raise ScreenshotExtractionError(str(exc)) from exc

        generated = sorted(Path(output_dir).glob("shot_*.png"))
        if not generated:
            raise ScreenshotExtractionError("No screenshots were generated")

        return self._build_metadata(generated[:expected_count], interval_seconds, duration)

    def _get_video_duration(self, video_path: str) -> float:
        try:
            probe = ffmpeg.probe(video_path)
            for stream in probe.get("streams", []):
                if stream.get("codec_type") == "video" and stream.get("duration"):
                    return float(stream["duration"])
            return float(probe.get("format", {}).get("duration", 0.0))
        except FileNotFoundError:
            return self._probe_duration_with_ffmpeg(video_path)
        except ffmpeg.Error as exc:  # type: ignore[attr-defined]
            logger.warning("Failed to probe video duration: %s", exc)
            return self._probe_duration_with_ffmpeg(video_path)

    def _probe_duration_with_ffmpeg(self, video_path: str) -> float:
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-i", video_path],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError:
            logger.warning("FFmpeg binary not available to probe duration")
            return 0.0

        output = result.stderr or result.stdout
        match = re.search(r"Duration: (?P<h>\d+):(?P<m>\d+):(?P<s>\d+(?:\.\d+)?)", output)
        if not match:
            return 0.0

        hours = int(match.group("h"))
        minutes = int(match.group("m"))
        seconds = float(match.group("s"))
        return hours * 3600 + minutes * 60 + seconds

    def _build_metadata(
        self,
        files: List[Path],
        interval_seconds: int,
        duration: float,
    ) -> List[ScreenshotEvidence]:
        screenshots: List[ScreenshotEvidence] = []
        for idx, path in enumerate(files):
            timestamp = min(duration, idx * interval_seconds)
            screenshots.append(
                ScreenshotEvidence(
                    index=idx,
                    path=str(path),
                    timestamp_seconds=float(timestamp),
                )
            )
        return screenshots


class GeminiVisionReviewer:
    """Geminiを用いてスクリーンショットからフィードバックを生成"""

    def __init__(
        self,
        model: str,
        temperature: float,
        max_output_tokens: int,
    ):
        self.model_name = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.rotation_manager = get_rotation_manager()

    def review(
        self,
        video_path: str,
        screenshots: List[ScreenshotEvidence],
        metadata: Optional[Dict[str, str]] = None,
    ) -> VideoReviewFeedback:
        if not screenshots:
            raise ValueError("screenshots must not be empty")

        prompt = self._build_prompt(video_path, screenshots, metadata)
        image_parts = []
        for shot in screenshots:
            with open(shot.path, "rb") as img_file:
                image_parts.append({"mime_type": "image/png", "data": img_file.read()})

        def api_call(api_key_value: str) -> str:
            genai.configure(api_key=api_key_value)
            model = genai.GenerativeModel(f"models/{self.model_name}")
            generation_config = genai.GenerationConfig(
                temperature=self.temperature,
                max_output_tokens=self.max_output_tokens,
                response_mime_type="application/json",
            )
            response = model.generate_content(
                [prompt, *image_parts],
                generation_config=generation_config,
            )
            return response.text

        try:
            raw_response = self.rotation_manager.execute_with_rotation(
                provider="gemini",
                api_call=api_call,
                max_attempts=3,
            )
        except Exception as exc:
            logger.error("Gemini review failed: %s", exc)
            raise

        try:
            data = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON from Gemini. Raw response: %s", raw_response[:500])
            raise ValueError("Gemini response was not valid JSON") from exc

        return VideoReviewFeedback(**data)

    def _build_prompt(
        self,
        video_path: str,
        screenshots: List[ScreenshotEvidence],
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        raw_title = metadata.get("title") if metadata else None
        raw_duration = metadata.get("duration") if metadata else None
        title = str(raw_title) if raw_title is not None else None
        duration = str(raw_duration) if raw_duration is not None else None
        screenshot_lines = [
            f"{idx + 1}. {shot.timestamp_label} ({os.path.basename(shot.path)})" for idx, shot in enumerate(screenshots)
        ]

        context_block = "\n".join(
            [
                "あなたは金融系YouTubeチャンネルの品質管理AIです。",
                "以下のスクリーンショットは動画を1分ごとにキャプチャしたものです。",
                "視聴維持率、画面のバリエーション、テロップやグラフの可読性を評価し、次の動画改善に繋がるフィードバックを返してください。",
                "視聴者は30代の投資家層で、最新ニュースを短時間で理解したいと考えています。",
            ]
        )

        video_info_line = f"動画タイトル: {title}" if title else "動画タイトル: 不明"
        duration_line = f"推定尺: {duration}" if duration else "推定尺: 未取得"
        screenshots_block = "\n".join(["スクリーンショット一覧:", *screenshot_lines])

        instructions = "\n".join(
            [
                "出力フォーマットは以下のJSON構造に従ってください:",
                "{",
                '  "summary": "動画全体の要約",',
                '  "positive_highlights": ["良かった点1", "良かった点2"],',
                '  "improvement_suggestions": ["改善案1", "改善案2"],',
                '  "retention_risks": ["離脱につながる懸念"],',
                '  "next_video_actions": ["次の動画で試すこと"]',
                "}",
                "日本語のみを使用し、簡潔かつ実行可能な提案にしてください。",
                "未知の場合は" "不明" "と記載せず、推測で埋めないでください。",
            ]
        )

        return "\n".join(
            [
                context_block,
                video_info_line,
                duration_line,
                screenshots_block,
                instructions,
            ]
        )


class VideoReviewService:
    """スクリーンショット抽出とAIフィードバックを統合するサービス"""

    def __init__(
        self,
        screenshot_extractor: Optional[VideoScreenshotExtractor] = None,
        reviewer: Optional[GeminiVisionReviewer] = None,
    ):
        review_settings = settings.video_review
        self.settings = review_settings
        self.screenshot_extractor = screenshot_extractor or VideoScreenshotExtractor()
        self.reviewer = reviewer or GeminiVisionReviewer(
            model=review_settings.model,
            temperature=review_settings.temperature,
            max_output_tokens=review_settings.max_output_tokens,
        )
        self.feedback_collector = get_feedback_collector() if review_settings.store_feedback else None

    def review_video(
        self,
        video_path: str,
        video_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        force_capture: bool = False,
    ) -> VideoReviewResult:
        if not self.settings.enabled:
            raise RuntimeError("Video review is disabled via configuration")

        base_name = video_id or Path(video_path).stem
        safe_dir_name = FileUtils.safe_filename(base_name)
        output_dir = os.path.join(self.settings.output_dir, safe_dir_name)

        screenshots = self.screenshot_extractor.extract(
            video_path=video_path,
            output_dir=output_dir,
            interval_seconds=self.settings.screenshot_interval_seconds,
            max_screenshots=self.settings.max_screenshots,
            force=force_capture,
        )

        feedback = self.reviewer.review(
            video_path=video_path,
            screenshots=screenshots,
            metadata=metadata,
        )

        result = VideoReviewResult(
            video_path=video_path,
            video_id=video_id,
            model_name=self.settings.model,
            screenshots=screenshots,
            feedback=feedback,
        )

        if self.feedback_collector and video_id:
            try:
                self.feedback_collector.record_ai_review(video_id, result)
            except Exception as exc:
                logger.warning("Failed to record AI review for %s: %s", video_id, exc)

        return result


_review_service_instance: Optional[VideoReviewService] = None


def get_video_review_service() -> VideoReviewService:
    """サービスシングルトンを取得"""
    global _review_service_instance
    if _review_service_instance is None:
        _review_service_instance = VideoReviewService()
    return _review_service_instance
