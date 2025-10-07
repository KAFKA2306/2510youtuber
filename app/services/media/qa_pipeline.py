"""Automated media QA pipeline for audio, subtitles, and video outputs."""

from __future__ import annotations

import json
import logging
import math
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydub import AudioSegment
from pydub.silence import detect_silence

from app.config import cfg
from app.models.qa import CheckStatus, MediaCheckResult, QualityGateReport
from app.services.media.fractions import FractionParser

logger = logging.getLogger(__name__)


class MediaQAError(Exception):
    """Raised when QA pipeline cannot complete."""


class MediaQAPipeline:
    """Runs domain-specific quality checks and persists reports."""

    def __init__(self, config, *, fraction_parser: Optional[FractionParser] = None):
        self.config = config
        self._ffmpeg_binary = getattr(cfg, "ffmpeg_path", "ffmpeg") or "ffmpeg"
        self._ffprobe_binary = "ffprobe"
        self._fraction_parser = fraction_parser or FractionParser()

    def run(
        self,
        *,
        run_id: str,
        mode: str,
        script_path: Optional[str],
        script_content: Optional[str],
        audio_path: Optional[str],
        subtitle_path: Optional[str],
        video_path: Optional[str],
    ) -> QualityGateReport:
        if not self.config.enabled:
            report = QualityGateReport(run_id=run_id, mode=mode)
            report.add_check(
                MediaCheckResult(
                    name="media_quality",
                    status=CheckStatus.SKIPPED,
                    blocking=False,
                    message="Media QA disabled in configuration",
                )
            )
            return report

        report = QualityGateReport(run_id=run_id, mode=mode)

        report.add_check(self._run_audio_checks(audio_path=audio_path))
        report.add_check(
            self._run_subtitle_checks(
                script_path=script_path,
                script_content=script_content,
                subtitle_path=subtitle_path,
            )
        )
        report.add_check(self._run_video_checks(video_path=video_path))

        try:
            report.report_path = str(self._persist_report(report))
        except Exception as exc:  # pragma: no cover - persistence failures should not block workflow
            logger.warning(f"Failed to persist QA report: {exc}")

        return report

    def should_block(self, report: QualityGateReport, *, mode: str) -> bool:
        gating = self.config.gating
        if not gating.enforce:
            return False
        if mode in gating.skip_modes:
            return False
        return bool(report.blocking_failures())

    # ------------------------------------------------------------------
    # Individual domain checks
    # ------------------------------------------------------------------

    def _run_audio_checks(self, *, audio_path: Optional[str]) -> MediaCheckResult:
        if not self.config.audio.enabled:
            return MediaCheckResult(
                name="audio_integrity",
                status=CheckStatus.SKIPPED,
                blocking=False,
                message="Audio QA disabled",
            )

        if not audio_path or not Path(audio_path).exists():
            status = CheckStatus.FAILED if self.config.gating.fail_on_missing_inputs else CheckStatus.SKIPPED
            return MediaCheckResult(
                name="audio_integrity",
                status=status,
                blocking=self.config.gating.fail_on_missing_inputs,
                message="Audio file missing",
            )

        try:
            segment = AudioSegment.from_file(audio_path)
        except Exception as exc:
            return MediaCheckResult(
                name="audio_integrity",
                status=CheckStatus.FAILED,
                message="Failed to decode audio",
                detail=str(exc),
            )

        duration_seconds = max(len(segment) / 1000.0, 0.001)
        rms_source = getattr(segment, "dBFS", -96.0)
        peak_source = getattr(segment, "max_dBFS", -96.0)
        rms_db = rms_source if (rms_source is not None and not math.isinf(rms_source)) else -96.0
        peak_db = peak_source if (peak_source is not None and not math.isinf(peak_source)) else -96.0

        min_silence_len = max(1, int(1000 * self.config.audio.max_silence_seconds))
        silence_thresh = rms_db - 16 if not math.isinf(rms_db) else -40.0
        try:
            silence_ranges = detect_silence(
                segment,
                min_silence_len=min_silence_len,
                silence_thresh=silence_thresh,
            )
        except Exception as exc:  # pragma: no cover - rare pydub backend errors
            logger.warning(f"detect_silence failed: {exc}")
            silence_ranges = []
        longest_silence = 0.0
        if silence_ranges:
            longest_silence = max((end - start) / 1000.0 for start, end in silence_ranges)

        issues = []
        if peak_db > self.config.audio.peak_dbfs_max:
            issues.append(f"peak {peak_db:.2f} dBFS exceeds {self.config.audio.peak_dbfs_max:.2f}")
        if rms_db < self.config.audio.rms_dbfs_min or rms_db > self.config.audio.rms_dbfs_max:
            issues.append(
                f"rms {rms_db:.2f} dBFS outside {self.config.audio.rms_dbfs_min:.2f}/"
                f"{self.config.audio.rms_dbfs_max:.2f}"
            )
        if longest_silence > self.config.audio.max_silence_seconds:
            issues.append(f"silence {longest_silence:.2f}s exceeds {self.config.audio.max_silence_seconds:.2f}s")

        status = CheckStatus.PASSED if not issues else CheckStatus.FAILED
        message = "Audio levels within tolerance" if not issues else "; ".join(issues)

        return MediaCheckResult(
            name="audio_integrity",
            status=status,
            message=message,
            metrics={
                "duration_seconds": round(duration_seconds, 3),
                "peak_dbfs": round(peak_db, 2),
                "rms_dbfs": round(rms_db, 2),
                "longest_silence_seconds": round(longest_silence, 3),
            },
        )

    def _run_subtitle_checks(
        self,
        *,
        script_path: Optional[str],
        script_content: Optional[str],
        subtitle_path: Optional[str],
    ) -> MediaCheckResult:
        if not self.config.subtitles.enabled:
            return MediaCheckResult(
                name="subtitle_alignment",
                status=CheckStatus.SKIPPED,
                blocking=False,
                message="Subtitle QA disabled",
            )

        if not subtitle_path or not Path(subtitle_path).exists():
            status = CheckStatus.FAILED if self.config.gating.fail_on_missing_inputs else CheckStatus.SKIPPED
            return MediaCheckResult(
                name="subtitle_alignment",
                status=status,
                blocking=self.config.gating.fail_on_missing_inputs,
                message="Subtitle file missing",
            )

        script_text = script_content
        if not script_text and script_path and Path(script_path).exists():
            try:
                script_text = Path(script_path).read_text(encoding="utf-8")
            except Exception as exc:
                logger.warning(f"Failed to read script file for QA: {exc}")
                script_text = None

        script_lines = [line.strip() for line in (script_text or "").splitlines() if line.strip()]
        subtitle_lines = self._load_subtitle_lines(subtitle_path)
        line_ratio = (len(subtitle_lines) / len(script_lines)) if script_lines else 1.0

        timing_data = self._load_subtitle_timings(subtitle_path)
        max_gap = self._calculate_max_gap_seconds(timing_data)

        issues = []
        if script_lines and line_ratio < self.config.subtitles.min_line_coverage:
            issues.append(f"coverage {line_ratio:.2f} below {self.config.subtitles.min_line_coverage:.2f}")
        if not script_lines:
            issues.append("script unavailable for coverage check")
        if max_gap > self.config.subtitles.max_timing_gap_seconds:
            issues.append(f"gap {max_gap:.2f}s exceeds {self.config.subtitles.max_timing_gap_seconds:.2f}s")

        if not issues:
            status = CheckStatus.PASSED
        elif not script_lines:
            status = CheckStatus.WARN
        else:
            status = CheckStatus.FAILED
        message = "Subtitles aligned" if not issues else "; ".join(issues)

        return MediaCheckResult(
            name="subtitle_alignment",
            status=status,
            message=message,
            metrics={
                "script_line_count": len(script_lines),
                "subtitle_line_count": len(subtitle_lines),
                "coverage_ratio": round(line_ratio, 3),
                "max_gap_seconds": round(max_gap, 3),
            },
            blocking=bool(script_lines),
        )

    def _run_video_checks(self, *, video_path: Optional[str]) -> MediaCheckResult:
        if not self.config.video.enabled:
            return MediaCheckResult(
                name="video_compliance",
                status=CheckStatus.SKIPPED,
                blocking=False,
                message="Video QA disabled",
            )

        if not video_path or not Path(video_path).exists():
            status = CheckStatus.FAILED if self.config.gating.fail_on_missing_inputs else CheckStatus.SKIPPED
            return MediaCheckResult(
                name="video_compliance",
                status=status,
                blocking=self.config.gating.fail_on_missing_inputs,
                message="Video file missing",
            )

        try:
            probe = subprocess.run(
                [
                    self._ffprobe_binary,
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height,r_frame_rate,bit_rate:format=duration,bit_rate",
                    "-of",
                    "json",
                    video_path,
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError:
            return MediaCheckResult(
                name="video_compliance",
                status=CheckStatus.SKIPPED,
                blocking=False,
                message="ffprobe not available",
            )
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.strip() or exc.stdout.strip()
            return MediaCheckResult(
                name="video_compliance",
                status=CheckStatus.FAILED,
                message="ffprobe analysis failed",
                detail=detail,
            )

        try:
            data = json.loads(probe.stdout)
        except json.JSONDecodeError as exc:
            return MediaCheckResult(
                name="video_compliance",
                status=CheckStatus.FAILED,
                message="Invalid ffprobe output",
                detail=str(exc),
            )

        stream = (data.get("streams") or [{}])[0]
        fmt = data.get("format", {})

        width = int(stream.get("width") or 0)
        height = int(stream.get("height") or 0)
        fps = self._parse_fraction(stream.get("r_frame_rate"))
        bitrate = self._extract_bitrate(stream.get("bit_rate"), fmt.get("bit_rate"))
        duration = float(fmt.get("duration") or 0.0)

        issues = []
        if (
            width != self.config.video.expected_resolution.width
            or height != self.config.video.expected_resolution.height
        ):
            issues.append(
                f"resolution {width}x{height} != {self.config.video.expected_resolution.width}x"
                f"{self.config.video.expected_resolution.height}"
            )
        if fps < self.config.video.min_fps or fps > self.config.video.max_fps:
            issues.append(f"fps {fps:.2f} outside {self.config.video.min_fps:.2f}-{self.config.video.max_fps:.2f}")
        if bitrate < self.config.video.min_bitrate_kbps:
            issues.append(f"bitrate {bitrate:.0f}kbps below {self.config.video.min_bitrate_kbps}kbps")
        if duration <= 0:
            issues.append("duration invalid")

        status = CheckStatus.PASSED if not issues else CheckStatus.FAILED
        message = "Video complies with spec" if not issues else "; ".join(issues)

        return MediaCheckResult(
            name="video_compliance",
            status=status,
            message=message,
            metrics={
                "width": width,
                "height": height,
                "fps": round(fps, 3),
                "bitrate_kbps": round(bitrate, 1),
                "duration_seconds": round(duration, 2),
            },
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_subtitle_lines(self, subtitle_path: str) -> list[str]:
        lines = []
        try:
            with open(subtitle_path, "r", encoding="utf-8") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line or line.isdigit() or "-->" in line:
                        continue
                    lines.append(line)
        except Exception as exc:
            logger.warning(f"Failed to read subtitle file: {exc}")
        return lines

    def _load_subtitle_timings(self, subtitle_path: str) -> list[tuple[float, float]]:
        timings = []
        pattern = re.compile(r"(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s+-->\s+(?P<end>\d{2}:\d{2}:\d{2},\d{3})")
        try:
            with open(subtitle_path, "r", encoding="utf-8") as handle:
                for raw_line in handle:
                    match = pattern.search(raw_line)
                    if not match:
                        continue
                    start = self._parse_timestamp(match.group("start"))
                    end = self._parse_timestamp(match.group("end"))
                    timings.append((start, end))
        except Exception as exc:
            logger.warning(f"Failed to parse subtitle timings: {exc}")
        return timings

    def _calculate_max_gap_seconds(self, timings: list[tuple[float, float]]) -> float:
        if not timings:
            return 0.0
        timings.sort(key=lambda item: item[0])
        largest_gap = 0.0
        previous_end = timings[0][1]
        for start, end in timings[1:]:
            gap = max(0.0, start - previous_end)
            if gap > largest_gap:
                largest_gap = gap
            previous_end = max(previous_end, end)
        return largest_gap

    def _parse_timestamp(self, value: str) -> float:
        hours, minutes, seconds_millis = value.split(":")
        seconds, millis = seconds_millis.split(",")
        total = (int(hours) * 3600) + (int(minutes) * 60) + int(seconds) + int(millis) / 1000.0
        return float(total)

    def _persist_report(self, report: QualityGateReport) -> Path:
        directory = Path(self.config.report_dir or "data/qa_reports")
        directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_run_id = re.sub(r"[^a-zA-Z0-9_-]+", "_", report.run_id)
        filename = f"qa_{safe_run_id}_{timestamp}.json"
        path = directory / filename
        payload = report.dict()
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        logger.info(f"Persisted QA report to {path}")
        return path

    def _parse_fraction(self, value: Optional[str]) -> float:
        result = self._fraction_parser.parse(value)
        if not result.is_valid and value:
            logger.debug("Failed to parse fraction '%s'; using default %s", value, result.value)
        return result.value

    def _extract_bitrate(self, stream_bitrate: Optional[str], format_bitrate: Optional[str]) -> float:
        for candidate in (stream_bitrate, format_bitrate):
            if candidate:
                try:
                    return float(candidate) / 1000.0
                except ValueError:
                    continue
        return 0.0
