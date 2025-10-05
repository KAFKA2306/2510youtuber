"""FFmpeg configuration helpers shared across media services."""

from __future__ import annotations

import logging
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Optional

from imageio_ffmpeg import get_ffmpeg_exe
from pydub import AudioSegment

logger = logging.getLogger(__name__)


class FFmpegConfigurationError(RuntimeError):
    """Raised when FFmpeg validation commands fail."""


def _resolve_ffmpeg_path(requested_path: Optional[str]) -> str:
    """Resolve the FFmpeg binary path from configuration or defaults."""

    candidate = (requested_path or "ffmpeg").strip() or "ffmpeg"

    resolved = shutil.which(candidate)
    if resolved:
        return resolved

    candidate_path = Path(candidate).expanduser()
    if candidate_path.exists():
        return str(candidate_path)

    raise FileNotFoundError(f"FFmpeg binary not found for '{candidate}'")


def _run_ffmpeg_command(cmd: list[str]) -> None:
    """Execute a lightweight FFmpeg command to validate availability."""

    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=5)
    except subprocess.TimeoutExpired as exc:
        joined = " ".join(cmd)
        raise FFmpegConfigurationError(f"Timed out while executing '{joined}'") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode(errors="ignore") if exc.stderr else ""
        joined = " ".join(cmd)
        raise FFmpegConfigurationError(f"FFmpeg command failed ({joined}): {stderr.strip()}") from exc
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"FFmpeg executable missing: {cmd[0]}") from exc


def _verify_ffmpeg_binary(binary: str) -> None:
    """Run a pair of diagnostic FFmpeg commands to ensure support."""

    diagnostics = (
        [binary, "-version"],
        [binary, "-hide_banner", "-filters"],
    )
    for cmd in diagnostics:
        _run_ffmpeg_command(cmd)


def _configure_pydub(binary: str) -> None:
    """Point pydub's AudioSegment helpers at the validated FFmpeg binary."""

    AudioSegment.converter = binary
    AudioSegment.ffmpeg = binary

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        sibling = Path(binary).with_name("ffprobe")
        if sibling.exists():
            ffprobe = str(sibling)

    if ffprobe:
        AudioSegment.ffprobe = ffprobe
    else:
        logger.debug("ffprobe binary not found alongside %s", binary)


@lru_cache(maxsize=None)
def ensure_ffmpeg_tooling(requested_path: Optional[str] = None) -> str:
    """Validate FFmpeg availability and align AudioSegment with the binary."""

    try:
        resolved = _resolve_ffmpeg_path(requested_path)
    except FileNotFoundError:
        candidate = (requested_path or "").strip()
        if candidate and candidate.lower() != "ffmpeg":
            raise

        try:
            resolved = get_ffmpeg_exe()
        except Exception as exc:  # pragma: no cover - defensive guard
            raise FileNotFoundError("FFmpeg binary could not be resolved via imageio-ffmpeg") from exc

        logger.info("FFmpeg binary resolved via imageio-ffmpeg at %s", resolved)

    _verify_ffmpeg_binary(resolved)
    _configure_pydub(resolved)
    logger.debug("FFmpeg configured for AudioSegment at %s", resolved)
    return resolved

